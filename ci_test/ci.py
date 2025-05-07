import csv
import glob
from logging import handlers
import argparse
import configparser
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import re
import platform
import shutil
import subprocess
from subprocess import PIPE
import sys
from pathlib import Path
import xml.etree.cElementTree as Et
from xml.dom import minidom
from toml import load, dump as dump_ci

dynamic_lib = ".dll" if platform.system() == "Windows" else ".so"
static_lib = ".lib" if platform.system() == "Windows" else ".a"


def parse_args(cfgs):
    parser = argparse.ArgumentParser(description="仓颉三方库功能集成脚本")
    sub_parser = parser.add_subparsers()
    coverage_parser = sub_parser.add_parser("coverage", help="生成覆盖率报告的命令")
    coverage_parser.set_defaults(func=coverage)
    coverage_parser.add_argument("--html", action='store_true', help="跑完用例之后执行的命令, 用于生成html覆盖率报告")
    coverage_parser.add_argument("-b", action='store_true', help="跑完用例之后执行的命令, 和--html一起合用, 用于生成html覆盖率分支覆盖报告")
    coverage_parser_optimize = coverage_parser.add_mutually_exclusive_group()
    coverage_parser_optimize.add_argument('--LLT', action='store_true', help="指定跑LLT用例覆盖率")
    coverage_parser_optimize.add_argument('--HLT', action='store_true', help="指定跑HLT用例覆盖率")
    clean_parser = sub_parser.add_parser("clean", help="清空缓存文件")
    clean_parser.set_defaults(func=clean)
    version_parser = sub_parser.add_parser("version", help="打印脚本版本信息")
    version_parser.set_defaults(func=print_version)
    version_parser.add_argument("--cangjie", action='store_true', help="打印仓颉项目版本")
    version_parser.add_argument("--cj-home", help="打印仓颉项目版本")

    build_parser = sub_parser.add_parser("build", help="用于构建整个项目的命令")
    build_parser.add_argument("--target", help="适用于ohos的命令")
    build_parser.add_argument("-f", "--full", action='store_true', help="是否是全量进行构建, 默认cjpm build -i")
    build_parser.add_argument("--coverage", action='store_true', help="是否使用覆盖率方式构建")
    build_parser.add_argument("--cj-home", help="设置仓颉环境路径")
    build_parser.add_argument("--stdx-home", help="设置仓颉环境路径")
    build_parser.set_defaults(func=build)

    test_parser = sub_parser.add_parser("test", help="用于LLT测试命令")
    test_parser_optimize = test_parser.add_mutually_exclusive_group()
    test_parser_optimize.add_argument("-O", help="编译构建优化选项")
    test_parser_optimize.add_argument("--coverage", action='store_true', help="跑测试用例是否用覆盖率方式测试")
    test_parser_path = test_parser.add_mutually_exclusive_group()
    test_parser_path.add_argument("--case", help="指定单跑一个用例")
    test_parser_path.add_argument("--target", help="适用于ohos")
    test_parser_path.add_argument("--clean", action='store_true', help="是否清空测试临时目录")
    test_parser_path.add_argument("-p","--path", help="指定跑一个文件夹, 适用于在test/LLT文件夹多个文件夹方式")
    test_parser.set_defaults(func=test)

    ut_parser = sub_parser.add_parser("ut", help="单元测试的命令")
    ut_parser.set_defaults(func=cangjie_ut)
    sub_ut_parser = ut_parser.add_mutually_exclusive_group()
    sub_sub_ut_parser = sub_ut_parser.add_mutually_exclusive_group()
    sub_sub_ut_parser.add_argument("--no-run", action='store_true', help='用来仅编译单元测试产物')
    sub_sub_ut_parser.add_argument("--skip-build", action='store_true', help='用来仅执行单元测试产物')
    sub_sub_ut_parser.add_argument("-j", '--jobs', type=int, help='<N> 用来指定并行编译的最大并发数，最终的最大并发数取 N 和 2倍 CPU 核数 的最小值')
    sub_sub_ut_parser.add_argument("-V", '--verbose', action='store_true', help='配置项开启后，会输出单元测试的日志')
    sub_sub_ut_parser.add_argument("-g", action='store_true', help='用来生成 debug 版本的单元测试产物')
    sub_sub_ut_parser.add_argument("--bench", action='store_true', help='用来指定只执行 @bench 宏修饰用例的测试结果')
    sub_sub_ut_parser.add_argument("--coverage", action='store_true', help='配合 cjcov 命令可以生成单元测试的覆盖率报告。使用 cjpm test --coverage 统计覆盖率时，源代码中的 main 不会再作为程序入口执行，因此会显示为未被覆盖。建议使用 cjpm test 之后，不再手写多余的 main')
    sub_sub_ut_parser.add_argument("--condition", type=str, help='指定后，可按条件透传 module.json/cjpm.toml 中的命令')
    sub_sub_ut_parser.add_argument("--target", type=str, help='指定后，可交叉编译生成目标平台的单元测试结果，module.json/cjpm.toml 中的配置可参考')
    sub_sub_ut_parser.add_argument("--filter", type=str, help='<value> 用于过滤测试的子集，value 的形式如下所示：--filter=* 匹配所有测试类  --filter=*.* 匹配所有测试类所有测试用例(结果和*相同)  --filter=*.*Test,*.*case* 匹配所有测试类中以 Test 结尾的用例，或者所有测试类中名字中带有 case 的测试用例'
                                                      '--filter=MyTest*.*Test,*.*case*,-*.*myTest 匹配所有 MyTest 开头测试类中以 Test 结尾的用例，或者名字中带有 case 的用例，或者名字中不带有 myTest 的测试用例')
    sub_sub_ut_parser.add_argument("--random-seed", type=int, help='<N> 用来指定随机种子的值')
    sub_sub_ut_parser.add_argument("--no-color", action='store_true', help=' 关闭控制台颜色显示')
    sub_sub_ut_parser.add_argument("--isolate-all", action='store_true', help='对所有用例进行独立测试（即单个用例单进程测试，详见标准库手册中的选项说明）')
    sub_sub_ut_parser.add_argument("--isolate-all-timeout", type=str, help='用于对所有用例进行独立测试（即单个用例单进程测试）并指定超时时间')
    sub_ut_parser.add_argument("-m", "--merage", action='store_true', help='该命令不能其他命令共存, 用于把UT测试用例和源码进行合并, 并把源码进行备份')
    sub_ut_parser.add_argument("-b", "--back", action='store_true', help='该命令不能其他命令共存, 和-m命令互为相反命令, 把UT测试用例和源码进行分开, 首先要保证test/UT中存在该测试用例')

    cjlint_parser = sub_parser.add_parser("cjlint", help="cjlint检查工具命令")
    cjlint_parser.set_defaults(func=cjlint_check)
    cjlint_parser.add_argument('--json', action='store_true', help="cjlint检查是否是json配置文件方式")
    cjlint_parser.add_argument('--csv', action='store_true', help="cjlint检查是否是csv配置文件方式")
    cjlint_parser.add_argument("--cj-home", help="设置仓颉环境路径")

    doc_parser = sub_parser.add_parser("doc", help="生成api文档的命令, 需要依赖cangjie-code-api2md仓库编译的二进制包")
    doc_parser.set_defaults(func=cangjie_doc)
    doc_parser.add_argument("-s", "--source", help='需要扫描的源码路径')
    doc_parser.add_argument("-o", "--output", help='需要生成的文件名, 生成文件位于当前执行命令的文件夹')
    doc_parser.add_argument("-c", "--clear", type=bool, default=False, help='是否生成文件时清空文件内容')

    cjtest_parser = sub_parser.add_parser("cjtest", help="HLT用例测试方式")
    cjtest_parser.set_defaults(func=cjtest)
    cjtest_parser.add_argument("--target", help="指定运行环境方式, ohos和其他环境")
    cjtest_parser_optimize = cjtest_parser.add_mutually_exclusive_group()
    cjtest_parser_optimize.add_argument("-O", help="HLT用例测试方式")
    cjtest_parser_optimize.add_argument("--coverage", action='store_true', help="HLT用例测试方式")
    cjtest_parser_path = cjtest_parser.add_mutually_exclusive_group()
    cjtest_parser_path.add_argument("--case", help="HLT用例测试方式")
    cjtest_parser_path.add_argument("-p", help="HLT用例测试方式")
    cjtest_parser.add_argument("--root", help="HLT用例测试方式")
    cjtest_parser_branch = cjtest_parser.add_mutually_exclusive_group()
    cjtest_parser_branch.add_argument("--clean", action='store_true', help="是否清空测试临时目录")
    cjtest_parser_branch.add_argument("--main", action='store_true', help="HLT用例测试方式")
    cjtest_parser_branch.add_argument("--fuzz", action='store_true', help="HLT用例测试方式")

    # fuzz_test
    fuzz_parser = sub_parser.add_parser("fuzz", help="fuzz测试用例方式")
    fuzz_parser.set_defaults(func=fuzz_test)
    fuzz_parser.add_argument("--root")
    fuzz_parser.add_argument("--case")
    fuzz_parser.add_argument("--clean", action='store_true', help="是否清空测试临时目录")
    fuzz_parser.add_argument("-p")

    bench_parser = sub_parser.add_parser("bench", help="性能用例测试方式, 会寻找test/bench文件夹是否存在性能用例")
    bench_parser.set_defaults(func=bench_mark)
    bench_parser.add_argument("--root", help="")
    bench_parser.add_argument("--case", help="")
    bench_parser.add_argument("--clean", action='store_true', help="是否清空测试临时目录")
    bench_parser.add_argument("-p", help="")

    ## 计算 DT个数方法
    count_parser = sub_parser.add_parser("count", help="默认会统计LLT和HLT总计的用例数")
    count_parser.set_defaults(func=count)
    count_parser.add_argument("--HLT", action='store_true', help="计算HLT用例数")
    count_parser.add_argument("--LLT", action='store_true', help="计算LLT用例数")

    # 新增 perf 生成火焰图方式
    perf_parser = sub_parser.add_parser("perf", help="PERF Generate Flame Graph Method")
    perf_parser.set_defaults(func=perf_test)
    perf_parser.add_argument("--case")

    par = parser.parse_args()
    par.CANGJIE_CI_TEST_CFGS = cfgs
    config_cjc(par)
    try:
        par.func(par)
    except KeyboardInterrupt:
        cfgs.LOG.info("用户中断程序异常退出.")
        exit(1)

def set_parse_args(parser_obj):

    pass


def perf_test(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    cfgs.LOG.info("请注意生成火焰图时需要开启O2编译选项优化. ")


def bench_mark(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.root:
        set_cjtest_path(args, cfgs, '3rd_party_root')
    if get_cjtest_path(args, cfgs, "") == "":
        cfgs.LOG.error("请设置 --root=${project} 再试.")
        exit(1)
    args.fuzz = args.target = None
    args.main = True
    args.optimize = '-O2'
    HLTtest(args, cfgs)

def count(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    count_func = 0
    if args.HLT or (not args.HLT and not args.LLT):
        llt = os.path.join(cfgs.HOME_DIR, "test", "LLT")
        for path, _, files in os.walk(llt):
            for f in files:
                if str(f).endswith('.cj'):
                    testcase = 0
                    with open(os.path.join(path, f), "r", encoding='UTF-8') as ff:
                        for line in ff.readlines():
                            if line.__contains__("@TestCase"):
                                testcase += 1
                    if testcase == 1:
                        count_func += 1
                    else:
                        count_func = count_func + 1 + testcase
    if args.LLT or (not args.HLT and not args.LLT):
        hlt = os.path.join(cfgs.HOME_DIR, "test", "HLT")
        for path, _, files in os.walk(hlt):
            for f in files:
                if str(f).endswith('.cj'):
                    testcase = 0
                    with open(os.path.join(path, f), "r", encoding='UTF-8') as ff:
                        for line in ff.readlines():
                            if line.__contains__("@TestCase"):
                                testcase += 1
                    count_func = count_func + testcase
    print(count_func)


def cjlint_check(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.json and args.csv:
        cfgs.LOG.error("生成文件方式只为一种.")
    if args.json:
        cjlint_run(args, cfgs, out_type='json')
    elif args.csv:
        cjlint_run(args, cfgs, out_type='csv')
    else:
        cjlint_run(args, cfgs)


def fuzz_test(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.root:
        set_cjtest_path(args, cfgs, '3rd_party_root')
    if get_cjtest_path(args, cfgs, "") == "":
        cfgs.LOG.error("请设置 --root=${project} 再试.")
        exit(1)
    args.p = args.target = args.main = None
    args.fuzz = True
    args.optimize = '-O0'
    HLTtest(args, cfgs)


def cjtest(args):
    #os.popen('{} -v'.format(master_cjc))
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.coverage:
        args.optimize = '-O0 --coverage'
    elif args.O is None:
        args.optimize = ' -O0'
    elif args.O not in {"0", "1", "2", "s", "z"}:
        cfgs.LOG.error(f"没有此优化选项的值:{args.O}")
        args.optimize = ' -O0'
    else:
        args.optimize = f" -O{args.O}"
    if args.root:
        if args.target:
            set_cjtest_path(args, cfgs, '3rd_party_root_ohos')
        else:
            set_cjtest_path(args, cfgs, '3rd_party_root')
    if args.target:
        if get_cjtest_path(args, cfgs, args.target) == "":
            cfgs.LOG.warn("请配置ohos的3rd_party_root")
        else:
            _get_DEVECO_CANGJIE_HOME(cfgs)
    else:
        if get_cjtest_path(args, cfgs, "") == "":
            cfgs.LOG.warn("请配置3rd_party_root, ciTest cjtest --root=CangjieObjectParentPath.")
    if cfgs.CANGJIE_STDX_PATH:
        cfgs.IMPORT_PATH += f" --import-path {Path(cfgs.CANGJIE_STDX_PATH).parent}"
        cfgs.LIBRARY_PATH += f" -L {cfgs.CANGJIE_STDX_PATH}"
        __improt_stdx_libs([cfgs.CANGJIE_STDX_PATH], cfgs)
    HLTtest(args, cfgs)


def print_version(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.cangjie:
        print(f"#{cfgs.EXPECT_CJC_VERSION}")
    else:
        cfgs.LOG.info("Cangjie Koolib Ci Test Version: 0.49.2.1")


def cangjie_ut(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    UT_test(args, cfgs)


def main(cfgs):
    cfgs.LOG = init_log(cfgs, "ci_test")
    parse_args(cfgs)


def clean(cfgs):
    cfgs.LOG.info("start clear")
    shutil.rmtree(cfgs.temp_dir, ignore_errors=True)
    shutil.rmtree(cfgs.log_dir, ignore_errors=True)
    cfgs.LOG.info("end clear")


def coverage(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    args.e = None
    args.coverage = True
    args.target = args.ohos_home = args.cj_home = args.case = args.ut = args.path = args.O2 = args.O1 = args.O0 = args.full = None
    if not args.html:
        args.root = args.main = args.p = args.fuzz = args.target = None
        build(args)
        if args.LLT:
            test(args)
        elif args.HLT:
            cjtest(args)
        else:
            test(args)
            args.HLT = True
            cjtest(args)
    build_coverage(args, cfgs)


def cangjie_doc(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if platform.system() == 'Windows':
        print("暂时不支持windows版本..")
        return
    if cfgs.BUILD_TYPE == "ci_test":
        dir = os.path.join(cfgs.FILE_ROOT, "cangjiedoc")
    else:
        dir = os.path.join(cfgs.BASE_DIR, "cangjiedoc")
    clear = 'false' if args.clear == False else "true"
    output = subprocess.Popen(
        '{} -s {} -o {} -c {}'.format(str(dir), args.source, args.output, clear), shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )
    log_output(output, output.args,cfgs)


def build(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.full:
        cfgs.LOG.info(f"清理build构建目录: {os.path.join(cfgs.HOME_DIR, cfgs.BUILD_BIN)}")
        shutil.rmtree(os.path.join(cfgs.HOME_DIR, cfgs.BUILD_BIN), ignore_errors=True)
    runBuild(args, cfgs)


def test(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    if args.path and args.case:
        cfgs.LOG.error("单跑用例和单跑指定文件夹, 不能同时设置. ")
        exit(1)
    elif args.path:
        if os.path.exists(args.path) :
            if not os.path.isabs(args.path):
                args.path = os.path.join(cfgs.HOME_DIR, args.path)
        else:
            cfgs.LOG.error("指定文件夹不存在. 请重试")
            exit(1)
    clean(cfgs)
    if args.coverage:
        args.optimize = ' -O0 --coverage'
    elif args.O is None:
        args.optimize = ' -O0'
    elif args.O not in {"0", "1", "2", "s", "z"}:
        cfgs.LOG.error(f"没有此优化选项的值:{args.O}")
        args.optimize = ' -O0'
    else:
        args.optimize = f" -O{args.O}"
    cfgs.Woff = ""
    try:
        version = os.popen('cjc -v').readline().split('Cangjie Compiler: ')[1].split(' (')[0]
        if float(version[2:-1]) >= 39.7:
            cfgs.Woff = " -Woff all"
    except:
        pass
    __find_cjpm_home_librarys(args, cfgs)
    runAll(args, cfgs)
    end_build(cfgs)


def __find_cjpm_home_librarys(args, cfgs):
    try:
        parms = load(os.path.join(cfgs.HOME_DIR, "cjpm.lock"))
        sss = ''
        for key, value in parms['requires'].items():
            for k,v in value.items():
                if k == 'commitId':
                    str_lib = __get_cjpm_library_cjpm_lock_foreign_requires_path(cfgs, os.path.join(cfgs.BUILD_CJPM_PATH, key, v))
                    sub_lib = os.path.join(cfgs.BUILD_CJPM_PATH, key, v, str_lib)
                    if os.path.exists(sub_lib):
                        sss = f' -L {sub_lib} '
                        __set_up_the_link_lib(cfgs, sub_lib)
                        sss += __improt_libs([sub_lib], cfgs)
                        if cfgs.OS_PLATFORM == "windows":
                            __get_windows_c_lib_arr(cfgs, sub_lib)
        str_lib = __get_cjpm_library_cjpm_lock_foreign_requires_path(cfgs, cfgs.HOME_DIR)
        sub_lib = os.path.join(cfgs.HOME_DIR, str_lib)
        if os.path.exists(sub_lib):
            sss = f' -L {sub_lib} '
            __set_up_the_link_lib(cfgs, sub_lib)
            sss += __improt_libs([sub_lib], cfgs)
            if cfgs.OS_PLATFORM == "windows":
                __get_windows_c_lib_arr(cfgs, sub_lib)
        cfgs.IMPORT_PATH += sss
    except:
        pass


def __get_windows_c_lib_arr(cfgs, sub_lib):
    for path, _, libs in os.walk(sub_lib):
        for lib in libs:
            if lib.startswith("lib") and lib.endswith(".dll"):
                cfgs.WINDOWS_C_LIB_ARR.add(os.path.join(path, lib))


def __get_cjpm_library_cjpm_lock_foreign_requires_path(cfgs, that_lib_path):
    if cfgs.BUILD_BIN != "build" and os.path.exists(os.path.join(that_lib_path,"cjpm.toml")):
        parm = load(os.path.join(that_lib_path,"cjpm.toml"))
        if parm.get('ffi') is not None:
            for key, value in parm['ffi'].items():
                if key == "c":
                    for ke, val in value.items():
                        for k, v in val.items():
                            if k == 'path':
                                return str(v).replace('./','').replace('/', os.path.sep)
    else:
        # json
        parm = json.load(open(os.patn.join(that_lib_path, "module.json"), 'r', encoding='UTF-8'))
        for ke, val in parm["foreign_requires"].items():
            for k, v in val.items():
                if k == 'path':
                    return str(v).replace('./','').replace('/', os.path.sep)
    return 'lib'


def config_cjc(args):
    cfgs = args.CANGJIE_CI_TEST_CFGS
    master_cjc = shutil.which("cjc")
    #使用命令行指定的cjc进行构建测试
    cfgs.BUILD_CJPM_PATH = get_cangjie_path(cfgs, 'cjpm')
    if cfgs.BUILD_CJPM_PATH == '':
        if cfgs.OS_PLATFORM == "windows":
            cfgs.BUILD_CJPM_PATH = str(os.path.join(os.getenv("LOCALAPPDATA"), '.cjpm', 'git'))
        else:
            cfgs.BUILD_CJPM_PATH = str(os.path.join(os.getenv("HOME"), '.cjpm', 'git'))
    if not master_cjc:
        try:
            set_cangjie_path(args, cfgs)
        except:
            pass
        cfgs.cj_home = get_cangjie_path(cfgs, 'home')
        if not cfgs.cj_home:
            cfgs.LOG.error("No Cangjie path set.")
        else:
            args.cj_home = cfgs.cj_home

        envsetup(args, cfgs)
        cfgs.LOG.info("There is no CJC compiler, configuring the default CJC compiler.")
    else:
        cfgs.LOG.info("The CJC compiler has been configured.")
    out = "".join(os.popen('{} -v'.format(shutil.which("cjc"))).readlines())
    cfgs.LOG.info(out)
    cfgs.BASE_CJC_VERSION = out.split('Cangjie Compiler: ')[1].split(' (')[0]
    h_cjc_version = cfgs.BASE_CJC_VERSION.split(".")
    cfgs.CANGJIE_TARGET = out.split('Target: ')[1].replace('\n', '').replace('\r', '')
    if int(h_cjc_version[0]) == 0:
        if int(h_cjc_version[1]) < 49:
            cfgs.set_build_bin("build")
            cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "build")
        else:
            cfgs.set_build_bin("target")
            cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "target")
    else:
        pass  ## TODO
    # config stdx for 0.60.*
    if not cfgs.CANGJIE_STDX_PATH:
        if int(h_cjc_version[0]) == 0 and int(h_cjc_version[1]) >= 60:
            cfgs.LOG.info("仓颉版本大于0.60.*, 需要检查stdx是否配置")
            if master_cjc:
                cfgs.LOG.info("当前环境变量已经设置仓颉, 检查CANGJIE_HOME中是否存在stdx")
                cfgs.CANGJIE_STDX_PATH = os.path.join(Path(master_cjc).parent.parent, "stdx", "dynamic", "stdx")
            else:
                cfgs.LOG.info("未配置仓颉环境, 正在配置指定的路径的stdx")
                if not os.path.exists(os.path.join(cfgs.cj_home, "stdx", cfgs.BASE_CJC_VERSION)):
                    cfgs.LOG.error(f"{os.path.join(cfgs.cj_home, 'stdx', cfgs.BASE_CJC_VERSION)} not found")
                else:
                    cfgs.CANGJIE_STDX_PATH = os.path.join(cfgs.cj_home, "stdx", cfgs.BASE_CJC_VERSION, "dynamic", "stdx")## 默认配置到cangjie_env下面stdx
            __set_cangjie_stdx_home(cfgs, cfgs.CANGJIE_STDX_PATH)
        else:
            cfgs.LOG.info("仓颉版本小于0.60.*")

    # read cjc version
    cfg = os.path.join(cfgs.HOME_DIR, cfgs.CONFIG_FILE)
    try:
        if str(cfgs.CONFIG_FILE).endswith('.toml'):
            parm = load(cfg)
            if parm.get('package') is not None:
                for key, value in parm['package'].items():
                    if key == "cjc-version":
                        cfgs.EXPECT_CJC_VERSION = value
        else:
            parm = json.load(open(cfg, 'r', encoding='UTF-8'))
            cfgs.EXPECT_CJC_VERSION = parm['cjc_version']
    except:
        cfgs.LOG.warn("本项目没有配置文件module.json和cjpm.toml")


def init_log(cfgs, name):
    """init log config"""
    parser_maple_test_config_file(cfgs)
    log_path = cfgs.BASE_DIR
    create_file(log_path)
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%m-%d %H:%M:%S")
    # sys.stdout.reconfigure(encoding='utf-8')
    streamhandler = logging.StreamHandler(sys.stdout)
    streamhandler.setLevel(logging.DEBUG)
    streamhandler.setFormatter(formatter)
    log.addHandler(streamhandler)
    filehandler = TimedRotatingFileHandler(
        os.path.join(log_path, "ci_test.log"), when="W6", interval=1, backupCount=60
    )
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    log.addHandler(filehandler)
    return log

def parser_maple_test_config_file(cfgs):
    cfg = read_config(complete_path(os.path.join(cfgs.BASE_DIR, "ci_test.cfg")))
    cfgs.temp_dir = complete_path(os.path.join(cfgs.BASE_DIR, get_config_value(cfg, "running", "temp_dir", default="../test_temp/run")))
    cfgs.log_dir = complete_path(os.path.join(cfgs.BASE_DIR, get_config_value(cfg, "logging", "name", default="../test_temp/log")))
    cfgs.level = get_config_value(cfg, "logging", "level", default="INFO")
    cfgs.BUILD_CI_TEST_CFG = cfg



###  BUILD
SRC_FILES = ""
OTHER_BUILD_DICT = {".sh": "bash", ".java": "java", ".py": "python3", ".go": "go"}
dynamic_lib = ".dll" if platform.system() == "Windows" else ".so"
static_lib = ".lib" if platform.system() == "Windows" else ".a"
lib_list = []


def build_coverage(args, cfgs):
    e = '' if args.e == None else args.e
    b = "" if args.b == None else "--branches"
    output = subprocess.Popen(
        'cjcov --root=./ -e "{}" --html-details -o output {}'.format(e, b), shell=True, stderr=PIPE, stdout=PIPE
    )
    log_output(output, output.args, cfgs)
    exit(output.returncode)


def __set_up_the_link_lib(cfgs, lib_path):
    if cfgs.OS_PLATFORM == "windows":
        os.environ['Path'] = f"{os.getenv('Path')};{lib_path}"
    else:
        os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:" + os.environ.get('LD_LIBRARY_PATH', "")
    pass


def __load_c_library(args, cfgs):
    ffi_lib = os.path.join(cfgs.HOME_DIR, "ci_test", f"lib_{cfgs.MODULE_NAME}")
    if not os.path.exists(ffi_lib):
        cmd = f"git clone -b lib_{cfgs.MODULE_NAME} https://gitcode.com/Cangjie-TPC/ci_lib.git {ffi_lib} --depth 1"
        output = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cfgs.HOME_DIR,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        log_output(output, output.args, cfgs)
    ffi_bin_path = os.path.join(ffi_lib, cfgs.OS_PLATFORM, 'lib', f"lib_{cfgs.MODULE_NAME}")
    if os.path.isdir(ffi_bin_path):
        entries = os.listdir(ffi_bin_path)
        if len(entries) == 1 and os.path.isdir(os.path.join(ffi_bin_path, entries[0])):
            if not os.path.exists(os.path.join(cfgs.HOME_DIR, cfgs.CUSTOM_MAP['ci_lib'])):
                os.mkdir(os.path.join(cfgs.HOME_DIR, cfgs.CUSTOM_MAP['ci_lib']))
            for files in os.listdir(os.path.join(ffi_bin_path, entries[0])):
                shutil.copyfile(os.path.join(ffi_bin_path, entries[0], files),
                                os.path.join(cfgs.HOME_DIR, cfgs.CUSTOM_MAP['ci_lib'], files))
        else:
            for entry in entries:
                shutil.copyfile(os.path.join(ffi_bin_path, entry), os.path.join(cfgs.HOME_DIR, cfgs.CUSTOM_MAP['ci_lib'], entry))
    else:
        cfgs.LOG.error("已配置ci_lib, clone时未找到该文件.")



# 删除后缀名文件
def delete_suffix_file(filepath, suffix_name):
    for file in os.listdir(filepath):
        if '.' in file and file.split('.')[-1] == suffix_name:
            os.remove(os.path.join(filepath, file))


def runBuild(args, cfgs):
    delete_suffix_file(cfgs.HOME_DIR, 'gcda')
    delete_suffix_file(cfgs.HOME_DIR, 'gcno')
    if cfgs.CUSTOM_MAP.get("ci_lib"):
        __load_c_library(args, cfgs)
    cfgs.LOG.info("Building with cjpm.....")
    cjpmbuild(args, cfgs)


def get_sublib_list(cfgs, path):
    global lib_list
    global dynamic_lib
    global static_lib
    sub_library_libdir = os.path.join(path, 'lib')
    if os.path.exists(sub_library_libdir):
        for path_2, dirs, files in os.walk(sub_library_libdir):
            for file in files:
                if dynamic_lib in str(file) or static_lib in str(file):
                    lib_list.append(str(os.path.join(path_2, file)))
    # for sub_lib in get_sublibrary_path(cfgs, path):
    #     get_sublib_list(cfgs, os.path.join(path, sub_lib))


def get_cjc_cpm(cfgs):
    try:
        version = os.popen('cjc -v').readline().split('Cangjie Compiler: ')[1].split(' (')[0]
        if float(version[0:4]) >= 0.38:
            return "cjpm"
        else:
            return 'cpm'
    except IndexError:
       cfgs.LOG.error("没有配置cangjie环境变量, 请配置后再试, ciTest build --cj-home=CangjiePath;")
       exit(1)


def cjpmbuild(args, cfgs):
    output = __do_cjpm_build(args, cfgs)
    out, err = log_output(output, output.args, cfgs, cfgs.HOME_DIR)
    set_build_log_warnings_count(cfgs, err)
    if "imports package 'stdx" in str(err):
        cfgs.LOG.info("Trying again using STDX package.")
        if cfgs.CANGJIE_STDX_PATH:
            stdx_lib = cfgs.CANGJIE_STDX_PATH
            if not os.path.exists(os.path.join(cfgs.CANGJIE_STDX_PATH, cfgs.BASE_CJC_VERSION)):
                cfgs.LOG.error(str(out))
                cfgs.LOG.error("cjpm build error..")
                exit(output.returncode)
            else:
                stdx_lib = os.path.join(cfgs.CANGJIE_STDX_PATH, cfgs.BASE_CJC_VERSION, "dynamic", "stdx")

            ci_test_cfg = cfgs.BUILD_PARMS
            ci_test_cfg_target = ci_test_cfg['target']
            if cfgs.CANGJIE_TARGET not in ci_test_cfg_target:
                ci_test_cfg_target[cfgs.CANGJIE_TARGET] = {"bin-dependencies": {"path-option": [stdx_lib]}}
                dump_ci(ci_test_cfg, open(os.path.join(cfgs.HOME_DIR, "cjpm.toml"), "w"))
            else:
                if "bin-dependencies" not in ci_test_cfg_target[cfgs.CANGJIE_TARGET]:
                    ci_test_cfg_target[cfgs.CANGJIE_TARGET]['bin-dependencies'] = {"path-option": [stdx_lib]}
                else:
                    if "path-option" not in ci_test_cfg_target[cfgs.CANGJIE_TARGET]['bin-dependencies']:
                        ci_test_cfg_target[cfgs.CANGJIE_TARGET]['bin-dependencies']["path-option"] = [stdx_lib]
                    else:
                        ci_test_cfg_target[cfgs.CANGJIE_TARGET]['bin-dependencies']["path-option"].append(stdx_lib)
            output = __do_cjpm_build(args, cfgs)
            out, err = log_output(output, output.args, cfgs, cfgs.HOME_DIR)
            set_build_log_warnings_count(cfgs, err)
            if output.returncode != 0 or (err and "build failed" in str(err)):
                cfgs.LOG.error(str(out))
                cfgs.LOG.error("cjpm build error..")
                exit(output.returncode)
        else:
            cfgs.LOG.error("No configuration of STDX package was found.")
    elif output.returncode != 0 or (err and "build failed" in str(err)):
        cfgs.LOG.error(str(out))
        cfgs.LOG.error("cjpm build error..")
        exit(output.returncode)



def __do_cjpm_build(args, cfgs):
    if args.full:
        cmd0 = "{} update".format(get_cjc_cpm(cfgs))
        output = subprocess.Popen(cmd0, shell=True, cwd=cfgs.HOME_DIR, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        _, err_log = log_output(output, output.args, cfgs, cfgs.HOME_DIR)
        if output.returncode != 0:
            if str(err_log).__contains__("can not find the library"):
                sub_librarys = []
                for item in re.split("\r?\n", err_log):
                    if item.__contains__("field at"):
                        sub_library = os.path.join(item.split('field at ')[1]).split("\\n")[0]
                        if sub_library.endswith("cjpm.toml") or sub_library.endswith("module.json"):
                            sub_librarys.append(os.path.dirname(sub_library))
                __loop_down_load_cjpm_librarys(cfgs, sub_librarys)
                output = subprocess.Popen(cmd0, shell=True, cwd=cfgs.HOME_DIR, stderr=subprocess.PIPE,
                                          stdout=subprocess.PIPE)
                _, err_log = log_output(output, output.args, cfgs, cfgs.HOME_DIR)
            else:
                cfgs.LOG.error("build fail")
        cmd1 = "{} build".format(get_cjc_cpm(cfgs))
    else:
        cmd1 = "{} build -i".format(get_cjc_cpm(cfgs))
    if args.coverage:
        cmd1 += " --coverage"
    if args.target and str(args.target).__contains__("ohos"):
        # 读取 DEVECO_CANGJIE_HOME 环境变量
        _get_DEVECO_CANGJIE_HOME(cfgs)
        cmd1 += " --target=aarch64-linux-ohos"
    return subprocess.Popen(cmd1, shell=True, cwd=cfgs.HOME_DIR, stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE)
    # return log_output(output, output.args,cfgs, cfgs.HOME_DIR)


def __loop_down_load_cjpm_librarys(cfgs, sub_librarys):
    # sub_librarys
    for sub_library in sub_librarys:
        sub_library_config_file = os.path.join(sub_library, cfgs.CONFIG_FILE)
        if cfgs.BUILD_BIN != "build":
            if str(sub_library_config_file).endswith("toml"):
                __cjpm_git_download_toml(cfgs, sub_library, sub_library_config_file)
            elif str(sub_library_config_file).endswith("json"):
                __cjpm_git_download_json(cfgs, sub_library, sub_library_config_file)
            else:
                cfgs.LOG.warn("没有项目工程配置文件, 请配置module.json或者cjpm.toml配置文件")
        else:
            __cjpm_git_download_json(cfgs, sub_library, sub_library_config_file)



def __cjpm_git_download_json(cfgs, sub_library, sub_library_config_file):
    file = open(sub_library_config_file, 'r', encoding='UTF-8')
    parm = json.load(file)
    ffi = parm["foreign_requires"]
    name = parm['name']
    gitee = "https://gitcode.com/Cangjie-TPC/ci_lib.git"
    for ke, val in ffi.items():
        for k, v in val.items():
            if k == 'path':
                cmd0 = f"git clone -b lib_{name} {gitee} {os.path.join(cfgs.BASE_DIR, f'lib_{name}')} --depth=1"
                output = subprocess.Popen(cmd0, shell=True, cwd=cfgs.BASE_DIR, stderr=subprocess.PIPE,
                                          stdout=subprocess.PIPE)
                log_output(output, output.args, cfgs, cfgs.HOME_DIR)
                old_dir = os.path.join(cfgs.BASE_DIR, "lib_{}".format(name), cfgs.OS_PLATFORM, "lib", f"lib_{name}")
                str_lib = __get_cjpm_library_cjpm_lock_foreign_requires_path(cfgs, sub_library)
                new_dir = os.path.join(sub_library, str_lib)
                try:
                    shutil.copytree(old_dir, new_dir)
                except:
                    shutil.rmtree(new_dir)
                    shutil.copytree(old_dir, new_dir)


def __cjpm_git_download_toml(cfgs, sub_library, sub_library_config_file):
    cfgs.LOG.info(f"check file {sub_library_config_file}")
    parm = load(sub_library_config_file)
    name = parm['package']['name']
    gitee = "https://gitcode.com/Cangjie-TPC/ci_lib.git"
    for key, value in parm['ffi'].items():
        if key == "c":
            for ke, val in value.items():
                for k, v in val.items():
                    if k == 'path':
                        cmd0 = f"git clone -b lib_{name} {gitee} {os.path.join(cfgs.BASE_DIR, f'lib_{name}')} --depth=1"
                        output = subprocess.Popen(cmd0, shell=True, cwd=cfgs.BASE_DIR, stderr=subprocess.PIPE,
                                         stdout=subprocess.PIPE)
                        log_output(output, output.args, cfgs, cfgs.HOME_DIR)
                        old_dir = os.path.join(cfgs.BASE_DIR, "lib_{}".format(name), cfgs.OS_PLATFORM, "lib", f"lib_{name}")
                        new_dir = os.path.join(sub_library, "lib")
                        try:
                            shutil.copytree(old_dir, new_dir)
                        except:
                            shutil.rmtree(new_dir)
                            shutil.copytree(old_dir, new_dir)



def envsetup(args, cfgs):
    if cfgs.EXPECT_CJC_VERSION:
        cjc_version = cfgs.EXPECT_CJC_VERSION
    else:
        cjc_version = get_cjc_version(os.path.join(cfgs.HOME_DIR, 'README.md'))
    master_cjc = shutil.which("cjc")
    try:
        h_cjc_version = cjc_version.split(".")
    except:
        h_cjc_version = None
    if h_cjc_version and int(h_cjc_version[0]) == 0:
        if int(h_cjc_version[1]) < 49:
            cfgs.set_build_bin("build")
            cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "build")
        else:
            cfgs.set_build_bin("target")
            cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "target")
    if h_cjc_version and master_cjc:
        out = os.popen('{} -v'.format(master_cjc))
        base_cjc_version = out.readline().split('Cangjie Compiler: ')[1].split(' (')[0]
        h_cjc_version = base_cjc_version.split(".")
        if int(h_cjc_version[0]) == 0:
            if int(h_cjc_version[1]) < 49:
                cfgs.set_build_bin("build")
                cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "build")
            else:
                cfgs.set_build_bin("target")
                cfgs.LIB_DIR = os.path.join(cfgs.HOME_DIR, "target")
        else:
            pass  ## TODO
        if cjc_version == base_cjc_version:
            cfgs.LOG.info("本地已经配置cjc版本:{} 与项目中配置版本: {} 一致".format(base_cjc_version, cjc_version))
            return True
        else:
            cfgs.LOG.warn("本地已经配置cjc版本:{}, 与项目中配置版本: {} 不一致".format(base_cjc_version, cjc_version))
            return True
    elif args.cj_home:
        lists = os.listdir(args.cj_home)
        env_cjc = ""
        for l in lists:
            if os.path.isdir(os.path.join(args.cj_home, l)):
                cfgs.LOG.info(f"find cjc : {l}")
                if cjc_version == l:
                    env_cjc = l
        if env_cjc != "":
            cjc_home = os.path.join(args.cj_home, env_cjc)
        else:
            # 使用 默认 最新cjc 版本
            max_version = 0 #float(str(lists[0]).replace(".", ""))
            index = 0
            for li in lists:
                try:
                    if len(lists[max_version]) == 6 and len(li) == 6:
                        if int(str(lists[max_version]).replace(".", "")) < int(str(li).replace(".", "")):
                            max_version = index
                    index += 1
                except:
                    index += 1
                    continue
            if lists[max_version] != "":
                cjc_home = os.path.join(args.cj_home, lists[max_version])
            # TODO

        set_cangjie_home(cfgs, cjc_home)
        cfgs.LOG.info(f"set cjc version: {env_cjc}")
        cfgs.LOG.info(os.popen('cjc -v').readline())
        return True
    else:
        cfgs.LOG.error("没有发现配置cjc, 请配置cjc环境后再试. 或者请在命令后加 --cj-home=$CANGJIE_HOME. ")
        return False


def set_cangjie_home(cfgs, cjc_home):
    if cfgs.OS_PLATFORM == "windows":
        cfgs.LOG.info("The current environment is Windows")
        cangjie_bin = os.path.join(cjc_home, 'bin')
        cangjie_tools = os.path.join(cjc_home, 'tools', 'bin')
        cangjie_runtime = os.path.join(cjc_home, 'runtime', 'lib', 'windows_x86_64_llvm')
        cangjie_path = ""
        if cangjie_runtime not in os.environ['Path']:
            cangjie_path += f'{cangjie_runtime};'
        if cangjie_bin not in os.environ['Path']:
            cangjie_path += f'{cangjie_bin};'
        if cangjie_tools not in os.environ['Path']:
            cangjie_path += f'{cangjie_tools};'
        os.environ['Path'] = f"{cangjie_path}{os.environ['Path']}"
        if not os.getenv('CANGJIE_HOME'):
            os.environ['CANGJIE_HOME'] = f"{cjc_home}"
    else:
        cfgs.LOG.info("The current environment is linux")
        os.environ['PATH'] = f"{cjc_home}/bin:{cjc_home}/tools/bin:{cjc_home}/debugger/bin:" + os.environ['PATH']
        os.environ['CANGJIE_HOME'] = f"{cjc_home}"
        os.environ[
            'LD_LIBRARY_PATH'] = f"{cjc_home}/runtime/lib/linux_x86_64_llvm:{cjc_home}/debugger/third_party/lldb/lib:" + os.environ.get(
            'LD_LIBRARY_PATH', "")


def __set_cangjie_stdx_home(cfgs, stdx_home):
    if cfgs.OS_PLATFORM == "windows":
        cangjie_stdx_path = ""
        if stdx_home not in os.environ['Path']:
            cangjie_stdx_path += f'{stdx_home};'
        os.environ['Path'] = f"{cangjie_stdx_path}{os.environ['Path']}"
    else:
        os.environ['LD_LIBRARY_PATH'] = f"{stdx_home}:" + os.environ.get('LD_LIBRARY_PATH', "")
    cfgs.LOG.info("set cangjie stdx success.")


def get_cjc_version(path):
    if not str(path).endswith('README.md'):
        return 0
    with open(path, "r", encoding='UTF-8') as file:
        strs = file.read()
        try:
            count = strs.split('cjc-v')[1].split('-brightgreen')[0]
            if not count:
                return 0
            else:
                return count
        except:
            return 0


def copy_windows_lib(args):
    args.WINDOWS_DLLS = []
    for root, _, files in os.walk(args.LIB_DIR):
        if not os.path.join(root).endswith("bin"):
            for dll in files:
                if str(dll).endswith(".dll"):
                    args.WINDOWS_DLLS.append(os.path.join(root, dll))


def find_lib_path(lib_path, ci_lib_path):
    cj_3rd_libs = set()
    """查找三方依赖库 """
    if ci_lib_path != "":  ## cjtest
        lib_path_parent = os.path.dirname(lib_path)
        ci_lib_path_parent = os.path.dirname(ci_lib_path)
        if os.path.exists(lib_path_parent) and not os.path.exists(lib_path):
            for dir in os.listdir(lib_path_parent):
                if str(dir) == "release":
                    for dd in os.listdir(os.path.join(lib_path_parent, "release")):
                        if str(dd).__contains__(".") or str(dd) == "bin":
                            continue
                        cj_3rd_libs.add(os.path.join(lib_path_parent, "release", dd))
                else:
                    if not str(dir).__contains__(".") and str(dir) != "bin":
                        cj_3rd_libs.add(os.path.join(lib_path_parent, dir))
        elif os.path.exists(lib_path):
            cj_3rd_libs.add(lib_path)
        elif os.path.exists(ci_lib_path_parent) and not os.path.exists(ci_lib_path):
            for dir in os.listdir(ci_lib_path_parent):
                if str(dir) == "release":
                    for dd in os.listdir(os.path.join(ci_lib_path_parent, "release")):
                        if str(dd).__contains__(".") or str(dd) == "bin":
                            continue
                        cj_3rd_libs.add(os.path.join(ci_lib_path_parent, "release", dd))
                else:
                    if not str(dir).__contains__(".") and str(dir) != "bin":
                        cj_3rd_libs.add(os.path.join(ci_lib_path_parent, "release"))
        elif os.path.exists(ci_lib_path):
            cj_3rd_libs.add(ci_lib_path)
    else:  ## LLT test
        if os.path.exists(os.path.join(lib_path, "release")):
            cj_3rd_libs.add(os.path.join(lib_path, "release"))
        elif os.path.exists(lib_path):
            cj_3rd_libs.add(lib_path)
        elif os.path.exists(ci_lib_path):
            cj_3rd_libs.add(ci_lib_path)
            if not os.path.exists(os.path.join(lib_path, "release")):
                for root, dirs, files in os.walk(ci_lib_path):
                    for dir_name in dirs:
                        if os.path.join(ci_lib_path, dir_name) in cj_3rd_libs:
                            continue
                        if os.path.exists(os.path.join(ci_lib_path, dir_name)):
                            cj_3rd_libs.add(os.path.join(ci_lib_path, dir_name))
    cangjie_env_setup(cj_3rd_libs)
    return cj_3rd_libs


def cangjie_env_setup(lib_dir):
    if platform.system() == "Windows":
        for item in lib_dir:
            if f"{item}" not in os.environ['Path']:
                os.environ['Path'] = f"{os.getenv('Path')};{item}"
    else:
        for item in lib_dir:
            if os.path.exists(item):
                if str(item) not in os.getenv('LD_LIBRARY_PATH'):
                    os.environ['LD_LIBRARY_PATH'] = f"{item}:{os.environ.get('LD_LIBRARY_PATH', '')}"

                # if str(item) not in os.getenv('CANGJIE_HOME'):
                #     os.environ["CANGJIE_HOME"] = f"{item}:{os.environ.get('CANGJIE_HOME', '')}"


def do_load_library_cfg(cfg_path):
    config = read_config(Path(cfg_path))
    return config['cangjie_library'], config['cangjie_library_branch']


def set_build_log_warnings_count(cfgs, err):
    try:
        len = str(err).count('[33mwarning')
        cfg = read_config(complete_path(choose_method(cfgs)))
        if cfg.has_section("build-warning"):
            cfg.set("build-warning", 'warning', str(len))
        else:
            cfg.add_section("build-warning")
            cfg.set("build-warning", 'warning', str(len))
        cfg.write(open(choose_method(cfgs), 'w', encoding='UTF-8'))
    except:
        pass


def set_cjtest_path(args, cfgs, target):
    cfg = read_config(complete_path(choose_method(cfgs)))
    cfg.set("test", target, args.root)
    cfg.write(open(choose_method(cfgs), 'w', encoding='UTF-8'))


def get_cjtest_path(args, cfgs, target):
    cfg = read_config(complete_path(choose_method(cfgs)))
    key = '3rd_party_root' if target != 'ohos' else '3rd_party_root_ohos'
    if cfg.has_section("test"):
        return cfg.get("test", key)


def get_cangjie_path(cfgs, p):
    cfg = read_config(complete_path(choose_method(cfgs)))
    if cfg.has_section("cangjie-home"):
        return cfg.get("cangjie-home", p)
    else:
        return None


def _get_DEVECO_CANGJIE_HOME(cfgs):
    cfg = read_config(complete_path(choose_method(cfgs)))
    try:
        if cfg.has_section("cangjie-home"):
            compile_option = cfg.get("cangjie-home", "OHOS_compile_option")
            if compile_option:
                print(compile_option)
                cfgs.OHOS_COMPILE_OPTION = compile_option
                return
            ohos_version = float(cfg.get("cangjie-home", "OHOS_version"))
            cfgs.OHOS_VERSION = ohos_version
            if ohos_version >= 4.0:
                temp = cfg.get("cangjie-home", "DEVECO_CANGJIE_HOME")
                os.environ["DEVECO_CANGJIE_HOME"] = temp
                cfgs.OHOS_CANGJIE_PATH = temp
            else:
                temp = cfg.get("cangjie-home", "OHOS_ROOT")
                os.environ["OHOS_ROOT"] = temp
                cfgs.OHOS_CANGJIE_PATH = temp
    except:
        cfgs.LOG.error("ohos环境设置失败.")
        return None


def set_cangjie_path(args, cfgs):
    cfg = read_config(complete_path(choose_method(cfgs)))
    if cfg.has_section("cangjie-home"):
        cfg.set("cangjie-home", 'home', args.cj_home)
    else:
        cfg.add_section("cangjie-home")
        cfg.set("cangjie-home", 'home', args.cj_home)
    cfg.write(open(choose_method(cfgs), 'w', encoding='UTF-8'))


def parser_run_config_file(run_config: Path):
    if not run_config or not run_config.exists() or not run_config.is_file():
        return None
    cfg = read_config(run_config)
    return {"shell": dict(cfg.items("shell")), "suffix": dict(cfg.items("suffix")),
            "internal_var": dict(cfg.items("internal_var"))}


def choose_method(cfgs):
    if cfgs.BUILD_TYPE == 'ci_test':
        return os.path.join(cfgs.FILE_ROOT, "ci_test.cfg")
    else:
        return os.path.join(cfgs.BASE_DIR, "ci_test.cfg")


def complete_path(path):
    """returns the canonical path of a path"""
    path = Path(path)
    if not path.exists():
        return Path(os.path.realpath(str(path)))
    return path.expanduser().resolve()


def split_and_complete_path(paths):
    """ Split the paths and returns the canonical path of each path"""
    canonicalPaths = []
    for path in paths.split(","):
        canonicalPaths.append(complete_path(path))
    return canonicalPaths


def read_config(file_path):
    if not file_path.exists() or not file_path.is_file():
        return None
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(str(file_path), encoding="utf-8")
    return config


def get_config_value(config, section, option, default=None):
    """read config value from test config"""
    try:
        return config[section][option]
    except:
        return default


def form_line(line, obj):
    for key, value in obj.items():
        end = 0
        while end < len(line):
            start = line.find("%{}".format(key), end)
            if start == -1:
                break
            end = len(key) + start + 1
            if end == len(line):
                line = line[:start] + value + line[end:]
            elif not line[end].isalnum() and line[end] != "_":
                line = line[:start] + value + line[end:]
            end = len(value) + start + 1
    return line


def filter_line(line, flag=None):
    """return the line starting with the flag"""
    if flag is None:
        return line
    line_flag = line.strip().split(":")[0].strip()
    if line_flag == flag:
        new_line = line.strip()[len(flag) + 1:].strip().lstrip(":").strip()
        return new_line
    return None


def cjlint_run(args, cfgs, out_type='json'):
    if os.path.exists("{}/report.{}".format(cfgs.HOME_DIR, out_type)):
        os.remove("{}/report.{}".format(cfgs.HOME_DIR, out_type))
        cfgs.LOG.info("删除旧文件....")
    if 'grpc' in str(cfgs.HOME_DIR):
        cmd = "cjlint -f {}/src -r {} -o {}/report".format(cfgs.HOME_DIR, out_type, cfgs.HOME_DIR)
        output = subprocess.Popen(cmd, shell=True, cwd=os.path.dirname(cfgs.HOME_DIR), stderr=PIPE, stdout=PIPE)
        log_output(output, output.args,cfgs, cfgs.HOME_DIR)
        if not os.path.exists("{}/report.{}".format(cfgs.HOME_DIR, out_type)):
            cfgs.LOG.info("check fail.")
            exit(1)
        cfgs.LOG.info("check success.")
    else:
        ohos_paths = []
        if os.path.exists(os.path.join(cfgs.HOME_DIR, "build-profile.json5")) :
            ohos_json = open(os.path.join(cfgs.HOME_DIR, "build-profile.json5"), "r", encoding='UTF-8')
            for line in ohos_json.readlines():
                if line.strip().startswith('"srcPath":'):
                    ss = line.strip().replace('"srcPath":', '').strip().replace(",", "").replace('"', "")
                    ohos_paths.append(ss)
        if len(ohos_paths) > 0:
            dicts = []
            for p in ohos_paths:
                if p == './entry' or p in 'entry':
                    continue
                try:
                    os.remove(os.path.join(cfgs.HOME_DIR, "report_temp.json"))
                except OSError:
                    pass
                cmd = f"cjlint -f {p}/src/main/cangjie/src -r {out_type} -o ./report_temp"
                output = subprocess.Popen(cmd, shell=True, cwd=cfgs.HOME_DIR, stderr=PIPE, stdout=PIPE)
                log_output(output, output.args, cfgs, cfgs.HOME_DIR)
                if output.returncode != 0:
                    exit(output.returncode)
                temp_json = json.load(open(os.path.join(cfgs.HOME_DIR, "report_temp.json"), "r", encoding='UTF-8'))
                dicts.extend(temp_json)
            json.dump(dicts, open(os.path.join(cfgs.HOME_DIR, 'report.json'), 'w'))
        else:
            cmd = "cjlint -f ./src -r {} -o ./report".format(out_type)
            output = subprocess.Popen(cmd, shell=True, cwd=cfgs.HOME_DIR, stderr=PIPE, stdout=PIPE)
            log_output(output, output.args, cfgs, cfgs.HOME_DIR)
        if not os.path.exists("{}/report.{}".format(cfgs.HOME_DIR, out_type)):
            cfgs.LOG.info("check fail.")
            exit(1)
        cfgs.LOG.info("check success.")


def pareFile(path):
    try:
        file = open(file=path, mode="r", errors='ignore')
        lines = file.readlines()
        dicts = {
            "EXEC": [],
            "RESOURCES": [],
            "DEPENDENCE": []
        }
        for item in lines:
            exec = filter_line(item, "// EXEC")
            dep = filter_line(item, "// DEPENDENCE")
            res = filter_line(item, "// RESOURCES")
            if exec:
                if platform.system() == 'Windows' and exec[:6] == './main':
                    exec = '.\\main.exe ' + exec[6:]
                dicts.get("EXEC").append(exec)
            if dep:
                for item2 in dep.split(" "):
                    if item2.strip():
                        dicts.get("DEPENDENCE").append(item2)
            if res:
                for item2 in res.split(" "):
                    if item2.strip():
                        dicts.get("RESOURCES").append(item2)
        else:
            file.close()
            return dicts
    except UnicodeDecodeError:
        return None


LIBS = []
TOTAL_CASES = 0
COUNT_CURRENT_CASE = 0

error_set = set()


def log_output(output, cmd, cfgs, filename=None):
    """ log command output"""
    cfgs.LOG.info("CMD    : %s", str(cmd))
    # cfgs.LOG.info("FILE   : %s", str(filename))
    stdout, stderr = output.communicate()
    encode = cfgs.ENCODING
    error = stderr.decode(encode, "ignore").strip()
    out = stdout.decode(encode, "ignore").strip()
    if error:
        for item in re.split("\r?\n", error):
            item = re.sub("\x1b\[\d+m", "", item)
            if output.returncode == 0:
                cfgs.LOG.warn(item)
            else:
                cfgs.LOG.error(item)
    if out:
        for item in re.split("\r?\n", out):
            cfgs.LOG.info(re.sub("\x1b\[\d+m", "", item))
    return out, error


def runAll(args, cfgs):
    subcmd = ""
    try:
        if args.coverage:
            subcmd = " --coverage"
    except:
        subcmd = ""
    cj_build_libs = find_lib_path(cfgs.LIB_DIR, '')
    find_cangjie_lib_arr = []
    for build_lib in cj_build_libs:
        cfgs.IMPORT_PATH += f" --import-path {build_lib}"
        for build_lib_item in os.listdir(build_lib):
            if build_lib_item.__contains__(".") or 'bin' in build_lib_item:
                continue
            if os.path.exists(os.path.join(build_lib, build_lib_item)):
                cfgs.LIBRARY_PATH += f" -L {os.path.join(build_lib, build_lib_item)}"
                find_cangjie_lib_arr.append(os.path.join(build_lib, build_lib_item))
                cangjie_env_setup(find_cangjie_lib_arr)
    if cfgs.CANGJIE_STDX_PATH:
        cfgs.IMPORT_PATH += f" --import-path {Path(cfgs.CANGJIE_STDX_PATH).parent}"
        cfgs.LIBRARY_PATH += f" -L {cfgs.CANGJIE_STDX_PATH}"
        __improt_stdx_libs([cfgs.CANGJIE_STDX_PATH], cfgs)
    __improt_libs(find_cangjie_lib_arr, cfgs)
    loop_dir(args, cfgs, lambda file: runOne(args, file, subcmd, cfgs))


def runOne(args, file, subcmd, cfgs):
    global RESULT
    path = Path(file)
    ci_lib_const = "ci_lib"
    ci_lib_dir = os.path.join(cfgs.HOME_DIR, ci_lib_const)
    global TOTAL_CASES, COUNT_CURRENT_CASE
    if path.is_file():
        name = (path.name + "_").split(".")
        name = "_".join(name)
        runPath = os.path.join(cfgs.temp_dir, name)
        lineDict = pareFile(file)
        if not lineDict:
            cfgs.LOG.warn("无法解析文件： {}".format(str(file)))
            return
        exec = lineDict.get("EXEC")
        copy = lineDict.get("DEPENDENCE")
        resources = lineDict.get("RESOURCES")
        copy.append(path.name)
        if cfgs.OS_PLATFORM and cfgs.OS_PLATFORM == "windows":
            copy_windows_lib(cfgs)
        if len(exec):
            create_file(runPath)
            source_file_path = os.path.join(cfgs.HOME_DIR, "test", "resources")
            os.environ['cangjie_test_path'] = str(source_file_path)
            for item in copy:
                try:
                    copy_path = path.parent
                    items = item.split('/')
                    for sps in items:
                        copy_path = os.path.join(copy_path, sps)
                    if os.path.isdir(copy_path):
                        shutil.copytree(copy_path, os.path.join(runPath, items[-1]))
                        shutil.copymode(copy_path, os.path.join(runPath, items[-1]))
                    else:
                        shutil.copyfile(copy_path, os.path.join(runPath, items[-1]))
                        shutil.copymode(copy_path, os.path.join(runPath, items[-1]))
                finally:
                    pass
            if cfgs.OS_PLATFORM and cfgs.OS_PLATFORM == "windows":
                if cfgs.WINDOWS_DLLS:
                    for dll in cfgs.WINDOWS_DLLS:
                        dll_name = dll.split(os.path.sep)[-1]
                        shutil.copyfile(dll, os.path.join(runPath, dll_name))
                if len(cfgs.WINDOWS_C_LIB_ARR) > 0:
                    for dll in cfgs.WINDOWS_C_LIB_ARR:
                        dll_name = dll.split(os.path.sep)[-1]
                        shutil.copyfile(dll, os.path.join(runPath, dll_name))
            for resource in resources:
                try:
                    copy_path = source_file_path
                    resource_split = resource.split('/')
                    for sps in resource_split:
                        copy_path = os.path.join(copy_path, sps)
                    shutil.copyfile(copy_path, os.path.join(runPath, resource_split[-1]))
                finally:
                    pass
            else:
                case_one_return_code = 0
                for item in exec:
                    cmd_temp = item
                    cmd = form_line(item, {"import-path": cfgs.IMPORT_PATH})
                    cmd = form_line(cmd, {"L": cfgs.LIBRARY_PATH})
                    cmd = form_line(cmd, {"l": cfgs.LIBRARY})
                    cmd = form_line(cmd, {"project-path": "--import-path {}".format(cfgs.HOME_DIR)})
                    cmd = form_line(cmd, {"project-L": "-L {}".format(cfgs.HOME_DIR)})
                    cmd = form_line(cmd, {"project": "{}".format(cfgs.HOME_DIR)})
                    if str(cmd) == str(cmd_temp):
                        sub_lib_cmd = get_library_cmd(cfgs, ci_lib_dir, ci_lib_const)
                        cmd = form_line(cmd, {"f": path.name + sub_lib_cmd})
                    else:
                        cmd = form_line(cmd, {"f": path.name})
                    if "cjc" in cmd:
                        cmd = cmd + subcmd + args.optimize + cfgs.Woff
                    output = subprocess.Popen(cmd, shell=True, cwd=runPath, stderr=subprocess.PIPE,
                                              stdout=subprocess.PIPE)
                    if platform.system() == 'Windows' and cmd != '.\\main.exe':
                        subprocess.Popen("cp {}/* {}".format(cfgs.LIB_DIR, runPath),
                                         shell=True, cwd=runPath, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    out, err = log_output(output, output.args, cfgs, path.name)

                    if output.returncode != 0:
                        case_one_return_code = output.returncode
                    elif "Summary: TOTAL:" in str(out):
                        out = re.sub("\x1b\[\d+m", "", str(out))
                        error = int(
                            str(out).split("Summary: TOTAL:")[1].split("ERROR: ")[1].split(cfgs.LINE_SEPARATOR)[0])
                        try:
                            failed = int( out.split("Summary: TOTAL:")[1].split("FAILED: ")[1].split(",")[0])
                        except ValueError:
                            failed = 0
                        if failed > 0 or error > 0:
                            case_one_return_code = 1
                else:
                    # remove runPath
                    if args.clean:
                        shutil.rmtree(runPath)
                    COUNT_CURRENT_CASE += 1
                    cfgs.LOG.info("return : %s", str(case_one_return_code))
                    cfgs.LOG.info(" >>=============================================<<当前进度{:.2f}% ".format(
                        float(COUNT_CURRENT_CASE) / float(TOTAL_CASES) * 100))
                    cfgs.LOG.info("")
                    if case_one_return_code != 0:
                        RESULT.get("FAIL").append(str(path))
                    else:
                        RESULT.get("PASS").append(str(path))


def __improt_libs(libsdir, cfgs=None, is_recursion=True):
    LLT_Link_libs = set()
    str = ""
    for sub_lib in libsdir:
        if is_recursion:
            for path, _, libs in os.walk(sub_lib):
                for lib in libs:
                    if lib.startswith("lib") and lib.endswith(".so"):
                        LLT_Link_libs.add(lib[3:len(lib) - 3])
                    elif lib.startswith("lib") and lib.endswith(".a"):
                        LLT_Link_libs.add(lib[3:len(lib) - 2])
                    elif platform.system() == 'Windows' and lib.startswith("lib") and lib.endswith(".dll"):
                        LLT_Link_libs.add(lib[3:len(lib) - 4])
        else:
            for so in glob.glob(os.path.join(sub_lib, "lib*.dll")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 4])
            for so in glob.glob(os.path.join(sub_lib, "lib*.so")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 3])
            for so in glob.glob(os.path.join(sub_lib, "lib*.a")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 2])
    if cfgs and len(cfgs.LIBRARY_PRIORITY) > 0:
        for ss in LLT_Link_libs:
            if not cfgs.LIBRARY_PRIORITY.__contains__(ss):
                cfgs.LIBRARY_PRIORITY.append(ss)
        LLT_Link_libs = cfgs.LIBRARY_PRIORITY
    for ss in LLT_Link_libs:
        cfgs.LIBRARY += "-l {} ".format(ss)
        str += "-l {} ".format(ss)
    return str


def __improt_stdx_libs(libsdir, cfgs=None, is_recursion=True):
    LLT_Link_libs = set()
    for sub_lib in libsdir:
        if is_recursion:
            for path, _, libs in os.walk(sub_lib):
                for lib in libs:
                    if lib.startswith("lib") and lib.endswith(".so"):
                        LLT_Link_libs.add(lib[3:len(lib) - 3])
                    elif lib.startswith("lib") and lib.endswith(".a"):
                        LLT_Link_libs.add(lib[3:len(lib) - 2])
                    elif platform.system() == 'Windows' and lib.startswith("lib") and lib.endswith(".dll"):
                        LLT_Link_libs.add(lib[3:len(lib) - 4])
        else:
            for so in glob.glob(os.path.join(sub_lib, "lib*.dll")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 4])
            for so in glob.glob(os.path.join(sub_lib, "lib*.so")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 3])
            for so in glob.glob(os.path.join(sub_lib, "lib*.a")):
                so = os.path.basename(so)
                LLT_Link_libs.add(so[3:len(so) - 2])
    if cfgs and len(cfgs.LIBRARY_PRIORITY) > 0:
        for ss in LLT_Link_libs:
            if not cfgs.LIBRARY_PRIORITY.__contains__(ss):
                cfgs.LIBRARY_PRIORITY.append(ss)
        LLT_Link_libs = cfgs.LIBRARY_PRIORITY
    for ss in LLT_Link_libs:
        if "stdx.fuzz.fuzz" not in ss:
            cfgs.LIBRARY += "-l {} ".format(ss)


def loop_dir(args, cfgs, callBack):
    currentDirectory = cfgs.TEST_DIR
    global TOTAL_CASES
    if args.path:
        if os.path.abspath(args.path).startswith(currentDirectory):
            currentDirectory = args.path
        else:
            cfgs.LOG.error("指定测试文件夹不是当前工程的子文件夹. 请重试")
            exit(1)
    for path, dirs, files in os.walk(currentDirectory):
        for item in files:
            if Path(item).suffix == ".cj":
                TOTAL_CASES += 1
    for path, dirs, files in os.walk(currentDirectory):
        for item in files:
            if Path(item).suffix == ".cj":
                if args.case:
                    if args.case.endswith(".cj"):
                        if args.case == str(item):
                            callBack(os.path.join(path, item))
                    else:
                        if "{}.cj".format(args.case) == str(item):
                            callBack(os.path.join(path, item))
                else:
                    callBack(os.path.join(path, item))


SRC_FILES = ""


def ut_result(out, err):
    arr = [-1, -1, -1, -1, -1]
    resu = str(out).split("TOTAL")[1].split("\\n")
    arr[0] = resu[0].split(": ")[1]
    res = resu[1].split(",")
    for item in res:
        if "PASSED" in item:
            arr[1] = item.split(": ")[1]
        elif "SKIPPED" in item:
            arr[2] = item.split(": ")[1]
        elif "ERROR" in item:
            arr[3] = item.split(": ")[1]
    if "FAILED" in resu[2]:
        arr[4] = resu[2].split(": ")[1].split(",")[0]
    if int(arr[3]) > 0 or int(arr[4]) > 0:
        RESULT.get("FAIL").append(str(arr[3]))
        RESULT.get("FAIL").append(str(arr[4]))
        raise Exception()


def create_file(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_library_cmd(cfgs, ci_lib_dir, ci_lib_const):
    my_libs_cmd = ""
    my_lib_dir = os.path.join(cfgs.HOME_DIR, ci_lib_const)
    dynamic_lib = ".dll" if platform.system() == "Windows" else ".so"
    static_lib = ".lib" if platform.system() == "Windows" else ".a"
    if os.path.exists(ci_lib_dir):
        for sub_lib_dir in os.listdir(ci_lib_dir):
            global LIB_DIR
            temp_lib_dir = os.path.join(ci_lib_dir, str(sub_lib_dir))
            if not Path(temp_lib_dir).is_file():
                LIB_DIR = temp_lib_dir
                my_libs = []
                for lib in os.listdir(LIB_DIR):
                    if lib.startswith("lib") and lib.endswith(dynamic_lib):
                        aa = lib[3:len(lib) - 3]
                        my_libs.append(aa)
                    elif lib.startswith("lib") and lib.endswith(static_lib):
                        aa = lib[3:len(lib) - 2]
                        my_libs.append(aa)
                for ss in my_libs:
                    my_libs_cmd = my_libs_cmd + "-l {} ".format(ss)

    return " --import-path {} -L {} {}".format(my_lib_dir, my_lib_dir, my_libs_cmd)


def UT_test(args, cfgs):
    try:
        if args.back:
            return
        shutil.copytree(cfgs.CANGJIE_SOURCE_DIR, os.path.join(cfgs.CI_TEST_DIR, 'src'), dirs_exist_ok=True)
        shutil.copytree(cfgs.UT_TEST_DIR, cfgs.CANGJIE_SOURCE_DIR, dirs_exist_ok=True)
        if args.merage:
            return
        cjpm_test_cmd = 'cjpm test '
        if args.no_run:
            cjpm_test_cmd += "--no-run "
        if args.skip_build:
            cjpm_test_cmd += "--skip-build "
        if args.jobs:
            cjpm_test_cmd += f"--jobs={args.jobs} "
        if args.verbose:
            cjpm_test_cmd += "--verbose "
        if args.g:
            cjpm_test_cmd += "-g "
        if args.bench:
            cjpm_test_cmd += "--bench "
        if args.coverage:
            cjpm_test_cmd += "--coverage "
        if args.condition:
            cjpm_test_cmd += f"--condition={args.condition} "
        if args.target:
            cjpm_test_cmd += f"--target={args.target} "
        if args.filter:
            cjpm_test_cmd += f"--filter={args.filter} "
        if args.random_seed:
            cjpm_test_cmd += f"--random-seed={args.random_seed} "
        if args.no_color:
            cjpm_test_cmd += "--no-color "
        if args.isolate_all:
            cjpm_test_cmd += "--isolate_all "
        if args.isolate_all_timeout:
            cjpm_test_cmd += "--isolate-all-timeout "

        cfgs.LOG.info(cjpm_test_cmd)
        return_code = cfgs.run_cmd(cjpm_test_cmd, file_dir=cfgs.HOME_DIR)
        exit(return_code)
    finally:
        if not args.merage:
            shutil.rmtree(cfgs.CANGJIE_SOURCE_DIR, ignore_errors=True)
            shutil.copytree(os.path.join(cfgs.CI_TEST_DIR, 'src'), cfgs.CANGJIE_SOURCE_DIR)


RESULT = {
    "FAIL": [],
    "PASS": []
}


def end_build(cfgs):
    cfgs.LOG.info(f"")
    for item in RESULT.get("FAIL"):
        cfgs.LOG.info(f"CASE: {item}, Result: FAIL")
    a = len(RESULT.get("FAIL"))
    b = len(RESULT.get("PASS"))
    cfgs.LOG.info("")
    cfgs.LOG.info("  TestSuiteTask: Total: {}, PASS: {}, FAIL: {}, Ratio  : {}%".format(str(a + b), str(b), str(a),
                                                                                        round(b / (a + b) * 100, 2) if (
                                                                                        a + b) > 0 else 0))
    if a:
        exit(1)


class Logger:
    def __init__(self, cfgs):
        self.cfgs = cfgs
        shutil.rmtree(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log"), ignore_errors=True)
        os.makedirs(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log", "split_log"), exist_ok=True)
        file_name = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log", "all.log")
        self.logger = cfgs.LOG
        self.logger.setLevel(logging.DEBUG)
        self.fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%m-%d %H:%M:%S")
        self.sh = logging.StreamHandler()
        self.sh.setFormatter(self.fmt)
        self.th = handlers.TimedRotatingFileHandler(filename=file_name, encoding="utf-8", when="D")
        self.th.setFormatter(self.fmt)
        self.case_th = None
        # self.logger.addHandler(self.sh)
        self.logger.addHandler(self.th)

    def info(self, msg):
        self.logger.info(msg.encode('gbk', 'ignore').decode('gbk'))

    def debug(self, msg):
        self.logger.debug(msg.encode('gbk', 'ignore').decode('gbk'))

    def error(self, msg):
        self.logger.error(msg.encode('gbk', 'ignore').decode('gbk'))

    def warning(self, msg):
        self.logger.warning(msg.encode('gbk', 'ignore').decode('gbk'))

    def setStream(self, file_name):
        dirs = file_name.split(os.sep)
        file_name = ".".join(dirs) if dirs[0] != "" else file_name
        log_file_name = os.path.join(self.cfgs.HOME_DIR, self.cfgs.CJ_TEST_WORK, "log", "split_log", file_name)
        if not os.path.exists(os.path.dirname(log_file_name)):
            os.makedirs(os.path.dirname(log_file_name))
            # os.makedirs(os.path.)
        if self.case_th is None:
            self.case_th = handlers.TimedRotatingFileHandler(filename=log_file_name, encoding="utf-8", when="D")
            self.case_th.setFormatter(self.fmt)
            self.logger.addHandler(self.case_th)
        if sys.version_info >= (3, 7):
            self.case_th.setStream(open(log_file_name, "a", encoding="utf-8"))
        else:
            self.case_th.stream = open(log_file_name, "a", encoding="utf-8")


# cfgs.CJ_TEST_WORK = ""

cp = configparser.ConfigParser()
cp.read(os.path.join(os.path.dirname(__file__), "ci_test.cfg"))
_3rd_party_root = ""

platform_str = sys.platform
ohos_dir = "/data/3rd/"
error_count = 0
total_count = 0
error_list = []


def get_cmd_info(file_name, target, cfgs):
    macro_cmd = ""
    dependence = ""

    run_option = ""
    is_valid_case = False
    with open(file_name, "r", encoding="utf-8") as f:
        case_dir = os.path.dirname(file_name)
        try:
            for line in f.readlines():
                if "3rd_party_lib:" in line and target != "ohos":
                    is_valid_case = True
                    line = line.replace("\n", "").replace(" ", "")
                    cj_3rd_lib_str = line[line.index("3rd_party_lib:") + 14:]
                    cj_3rd_libs_tmp = cj_3rd_lib_str.split(":")
                    cj_3rd_libs = None
                    for lib in cj_3rd_libs_tmp:
                        dirs = lib.replace('/', os.sep).split(os.sep)
                        index_build = 0
                        if cfgs.BUILD_BIN != "build":
                            for i in range(len(dirs)):
                                if dirs[i] == "build":
                                    index_build = i + 1
                                    dirs[i] = cfgs.BUILD_BIN
                        lib_path = os.path.join(_3rd_party_root, *dirs)
                        dirs[0] = "source"  # for ci
                        ci_lib_path = os.path.join(_3rd_party_root, *dirs)
                        cj_3rd_libs = find_lib_path(lib_path, ci_lib_path)
                    logger.info(f"find 3rd party libs in {cj_3rd_libs}")
                    for lib in cj_3rd_libs:
                        # send so files to ohos device
                        if lib not in cfgs.libs_3rd:
                            cfgs.libs_3rd.append(lib)
                            so_str = __improt_libs([lib], cfgs, False)
                            if so_str != "":
                                cfgs.import_cmd.add(os.path.realpath(os.path.join(lib, "..")))
                                cfgs.library_path_L_cmd.append(lib)
                                cfgs.library_l_cmd += so_str
                elif "3rd_party_lib_ohos:" in line and target == "ohos":
                    is_valid_case = True
                    line = line.replace("\n", "").replace(" ", "")
                    cj_3rd_lib_str = line[line.index("3rd_party_lib_ohos:") + 19:]
                    cj_3rd_libs_tmp = cj_3rd_lib_str.split(":")
                    cj_3rd_libs = []
                    for lib in cj_3rd_libs_tmp:
                        lib_path = os.path.join(_3rd_party_root, lib)
                        dirs = lib.split(os.sep)
                        dirs[0] = "source"  # for ci
                        ci_lib_path = os.path.join(_3rd_party_root, *dirs)
                        cj_3rd_libs = find_lib_path(lib_path, ci_lib_path)
                    logger.info(f"find 3rd party libs in {cj_3rd_libs}")

                    for lib in cj_3rd_libs:
                        # send so files to ohos device
                        if lib not in cfgs.libs_3rd:
                            cfgs.libs_3rd.append(lib)
                            so_str = __improt_libs([lib], cfgs, False)
                            if so_str != "":
                                cfgs.import_cmd.add(os.path.realpath(os.path.join(lib, "..")))
                                cfgs.library_path_L_cmd.append(lib)
                                cfgs.library_l_cmd += so_str


                elif "macro-lib:" in line:
                    if platform_str == "win32":
                        line = line.replace(".so", ".dll").replace("/", "\\")
                    is_valid_case = True
                    line = line.replace("\n", "").replace(" ", "")
                    marco_lib_str = line[line.index("macro-lib:") + 10:]
                    marco_libs_tmp = marco_lib_str.split(":")
                    marco_libs = []
                    for lib in marco_libs_tmp:
                        lib_path = os.path.join(_3rd_party_root, lib)
                        dirs = lib.split(os.sep)
                        dirs[0] = "source"  # for ci
                        ci_lib_path = os.path.join(_3rd_party_root, *dirs)
                        marco_libs = find_lib_path(lib_path, ci_lib_path)
                    for lib in marco_libs:
                        macro_cmd += f"{lib} "
                elif "dependence:" in line:
                    is_valid_case = True
                    dependence += " " + line[line.index("dependence:") + 11:].replace("\n", "").strip()
                    dependence = dependence.replace(":", " ").strip()
                    if case_dir != "":
                        if len(dependence.split(" ")) > 1:
                            tdep = ''
                            for dep in dependence.split(" "):
                                if dep:
                                    tdep += f' {os.path.join(case_dir, dep)} '
                            dependence = tdep
                        else:
                            dependence = f"{case_dir}/" + dependence
                elif "data_file:" in line:
                    is_valid_case = True
                    line = line.replace("\n", "").replace(" ", "")
                    data_file_str = line[line.index("data_file:") + 10:]
                    logger.info(f"data_file Start to copy data files")
                    if target != "ohos":
                        for data in data_file_str.split(":"):
                            src = os.path.join(os.path.dirname(file_name), data)
                            dst = os.path.join(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "tmp",
                                                            os.path.dirname(file_name).replace(cfgs.HOME_DIR,
                                                                                               ".")), data)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            logger.info(f"copy {src} to {dst}")
                            if os.path.isdir(src):
                                try:
                                    shutil.copytree(src, dst)
                                except:
                                    try:
                                        os.rmdir(dst)
                                        shutil.copytree(src, dst)
                                    except:
                                        logger.info(f"file existed")
                            else:
                                shutil.copy(src, dst)
                    else:
                        for data in data_file_str.split(":"):
                            src = os.path.join(os.path.dirname(file_name), data)
                            if os.path.exists(src):
                                dst = os.path.dirname(os.path.join(ohos_dir, data))
                                logger.info(f"hdc shell mkdir -p {dst}")
                                cfgs.run_cmd(f"hdc shell mkdir -p {dst}")
                                logger.info(f"hdc file send {src.replace('/', os.path.sep)} {dst}")
                                cfgs.run_cmd(f"hdc file send {src.replace('/', os.path.sep)} {dst}")
                elif "sources_file:" in line:
                    is_valid_case = True
                    line = line.replace("\n", "").replace(" ", "")
                    sources_file_str = line[line.index("sources_file:") + 12:]
                    logger.info(f"[{file_name}]: sources_file Start to copy sources files")
                    if target != "ohos":
                        for data in sources_file_str.split(":"):
                            if not len(data) == 0:
                                src = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "resources", data)
                                dst = os.path.join(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "tmp",
                                                                os.path.dirname(file_name).replace(cfgs.HOME_DIR,
                                                                                                   ".")), data)
                                logger.info(f"copy {src} to {dst}")
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                if os.path.isdir(src):
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy(src, dst)
                    else:
                        for data in sources_file_str.split(":"):
                            if not len(data) == 0:
                                src = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "resources", data)
                                dst = os.path.dirname(os.path.join(ohos_dir, data))
                                logger.info(f"hdc shell mkdir -p {dst}")
                                cfgs.run_cmd(f"hdc shell mkdir -p {dst}")
                                logger.info(f"hdc file send {src.replace('/', os.path.sep)} {dst}")
                                cfgs.run_cmd(f"hdc file send {src.replace('/', os.path.sep)} {dst}")
                elif "run_option:" in line:
                    is_valid_case = True
                    run_option += line[line.index('run_option:') + 11:].replace(":", " ")
        except UnicodeDecodeError:
            logger.error("'utf-8' codec can't decode byte 0xff in position 0: invalid start byte:>>" + file_name)

    macro_cmd = f"--macro-lib=\"{macro_cmd}\"" if macro_cmd != "" else ""

    return run_option, dependence, macro_cmd, is_valid_case


def run_one_case(args, file_path, run_option, compile_option, target, cfgs):
    global error_count
    global total_count
    global error_list
    logger.setStream(f"{os.path.basename(file_path)}.log")
    target_cmd = ""
    if target == "ohos":
        if cfgs.OHOS_VERSION >= 4.0: # 4.0 使用 deveco
            if cfgs.OHOS_CANGJIE_PATH is None:
                logger.error("please set OHOS_ROOT")
                return
            target_cmd = f"--target=aarch64-linux-ohos {cfgs.OHOS_CMD}"
        else: # 4.0 一下 使用 原始工具链
            if cfgs.OHOS_CANGJIE_PATH is None:
                logger.error("please set OHOS_ROOT")
                return
            ohos_root = cfgs.OHOS_CANGJIE_PATH
            target_cmd = f"--target=aarch64-linux-ohos " \
                         f"-B{ohos_root}/out/rk3568/obj/third_party/musl/usr/lib/aarch64-linux-ohos " \
                         f"-B{ohos_root}/prebuilts/clang/ohos/linux-x86_64/llvm/bin " \
                         f"-L{ohos_root}/prebuilts/clang/ohos/linux-x86_64/llvm/lib/clang/12.0.1/lib/aarch64-linux-ohos " \
                         f"-L{ohos_root}/prebuilts/clang/ohos/linux-x86_64/llvm/lib/aarch64-linux-ohos " \
                         f"-L{ohos_root}/out/rk3568/obj/third_party/musl/usr/lib/aarch64-linux-ohos " \
                         f"--sysroot {ohos_root}/out/rk3568/obj/third_party/musl "

        # run_cmd(f"hdc shell mkdir {ohos_dir};chmod -R 777 {ohos_dir}")

    case_run_option, dependence, macro_cmd, is_valid_case = get_cmd_info(file_path, target, cfgs)
    if not is_valid_case:
        logger.warning(f"{file_path} is a invalid case, skip.")
        return
    run_option += f" {case_run_option}"
    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    case_dir = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "tmp", file_dir.replace(cfgs.HOME_DIR, "."))
    logger.info(f"************************Start to run case file: {file_path}************************")
    os.makedirs(case_dir, exist_ok=True)
    if cfgs.OS_PLATFORM and cfgs.OS_PLATFORM == "windows":
        if cfgs.WINDOWS_DLLS:
            for dll in cfgs.WINDOWS_DLLS:
                dll_name = dll.split(os.path.sep)[-1]
                if os.path.exists(os.path.join(case_dir, dll_name)):
                    break
                shutil.copyfile(dll, os.path.join(case_dir, dll_name))
        if len(cfgs.WINDOWS_C_LIB_ARR) > 0:
            for dll in cfgs.WINDOWS_C_LIB_ARR:
                dll_name = dll.split(os.path.sep)[-1]
                if os.path.exists(os.path.join(case_dir, dll_name)):
                    break
                shutil.copyfile(dll, os.path.join(case_dir, dll_name))
    out = os.path.join(case_dir, f"{file_name}.out")
    case_import_cmd = '" --import-path="'
    case_library_path_L_cmd = " -L "
    compile_cmd = f'cjc {cfgs.Woff} {args.optimize} {target_cmd} {macro_cmd} ' \
                  f'--import-path="{case_import_cmd.join(cfgs.import_cmd)}" {cfgs.IMPORT_PATH} ' \
                  f'-L {case_library_path_L_cmd.join(cfgs.library_path_L_cmd)} {cfgs.LIBRARY_PATH} ' \
                  f'{cfgs.LIBRARY}' \
                  f'{cfgs.library_l_cmd} ' \
                  f'{file_path} {dependence} -o {os.path.realpath(out)} {compile_option}'
    logger.info(f"[Run CMD]{compile_cmd}")
    code = cfgs.run_cmd(compile_cmd)
    if code != 0:
        error_count += 1
        total_count += 1
        error_list.append(file_path)
        return
    out_dir = os.path.dirname(out)
    out_file = os.path.basename(out)

    fuzz_cmd = ""
    if args.fuzz:
        fuzz_cmd = f"-runs={args.fuzz_runs} -rss_limit_mb={args.fuzz_rss_limit_mb}"

    if target == "ohos":
        # send test file to ohos device
        if platform_str == "linux":
            cfgs.run_cmd(f"cd {out_dir};for f in `ls`;do hdc file send $f {ohos_dir};done")
        else:  # windows
            cfgs.run_cmd(f"cd {out_dir}&for %f in (*.*) do hdc file send %f {ohos_dir}")
        run_case_cmd = f"hdc shell cd {ohos_dir};chmod -R 777 *;export LD_LIBRARY_PATH={ohos_dir};./{out_file}"
    else:
        if platform_str == "linux":
            run_case_cmd = f"cd {out_dir};./{out_file} {run_option} {fuzz_cmd} -timeout=10800"  # -rss_limit_mb=16384
        else:  # windows
            run_case_cmd = f"cd {out_dir}&{out_file} {run_option} {fuzz_cmd}"
    logger.info(f"[Run CMD]{run_case_cmd}")
    return_code = cfgs.run_cmd(run_case_cmd)
    if args.clean:
        for root_p, _, out_dir_files in os.walk(out_dir):
            for out_dir_files_file_name in out_dir_files:
                os.remove(os.path.join(root_p, out_dir_files_file_name))
    if return_code != 0:
        logger.error(f"return === {return_code}")
        total_count += 1
        error_count += 1
        error_list.append(file_path)


def get_cases(cfgs):
    cases = {}  # {test_class:[[case, status, case_time_elapsed, error_trace]]}
    tcs_time = {}  # {test_class: tcs_time_elapsed}
    for log in glob.glob(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log", "split_log", "*.log")):
        pkg = log[14:-7]
        tcs = None
        with open(log, "r", encoding="utf-8") as f:
            lines = f.readlines()
            log_str = "".join(lines)
            log_str = re.sub("\x1b\[\d+m", "", log_str)
            i = 0
            while i < len(lines):
                line = re.sub("\x1b\[\d+m", "", lines[i])
                step = 1
                tcs_match_obj = re.match(r".* TCS: (.*), time elapsed: (.*) ns, RESULT:", line)
                if tcs_match_obj:
                    tcs = f"{pkg}.{tcs_match_obj.group(1)}"
                    tcs_time_elapsed = tcs_match_obj.group(2)

                    cases[tcs] = []
                    tcs_time[tcs] = float(tcs_time_elapsed)
                case_match_obj = re.match(r".* \[(.*)\] CASE: (\w*)( \((\d+) ns(, (\d+\.\d+|\d*) ns/op)?\))?", line)
                if case_match_obj:
                    status = case_match_obj.group(1)
                    case = case_match_obj.group(2)
                    case_time_elapsed = case_match_obj.group(4) if case_match_obj.group(4) is not None else 0
                    case_time_per_op = case_match_obj.group(6)
                    error_trace = ""

                    if "FAILED" in status or "ERROR" in status:
                        for j in range(i + 1, len(lines)):
                            next_line = re.sub("\x1b\[\d+m", "", lines[j])
                            tcs_mo = re.match(r".* TCS: (.*), time elapsed: (.*) ns, RESULT:", next_line)
                            case_mo = re.match(r".* \[(.*)\] CASE: (.*) \((.*) ns\)", next_line)
                            not_summary = "Summary: TOTAL" not in next_line
                            if tcs_mo is None and case_mo is None and not_summary:
                                step += 1
                                error_trace += next_line[33:]
                            else:
                                break
                    if tcs:
                        cases[tcs].append([case, status, float(case_time_elapsed), error_trace, case_time_per_op])
                i += step
        # compile error： get testcase count, and set Error
        if tcs is None:
            case_file = f"{pkg.replace('.', '/')}.cj"
            if not os.path.exists(case_file):
                continue
            with open(f"{pkg.replace('.', '/')}.cj", "r", encoding="utf-8") as cf:
                try:
                    lines = cf.readlines()
                except UnicodeDecodeError:
                    logger.error("'utf-8' codec can't decode byte 0xff in position 0: invalid start byte:>>")
                error_trace = log_str
            for i, line in enumerate(lines):
                if i == len(lines) - 1:
                    break
                next_line = lines[i + 1]
                if "@TestCase" in line and line.strip().startswith("@"):
                    case_match_obj = re.match(r".*func (.*)\(\)", next_line)
                    if case_match_obj:
                        case_name = case_match_obj.group(1)
                        cases[tcs].append([case_name, "ERROR", 0.0, error_trace, 0.0])
                elif "@Test" in line and line.strip().startswith("@"):
                    tcs_match_obj = re.match(r".*public class (.*){", next_line)
                    tcs_func_match_obj = re.match(r".*func (.*)\(\)", next_line)
                    if tcs_match_obj:
                        tcs = f"{pkg}.{tcs_match_obj.group(1)}"
                        if tcs not in cases.keys():
                            cases[tcs] = []
                        tcs_time[tcs] = 0.0
                    # Top-Level @Test func
                    elif tcs_func_match_obj:
                        tcs = f"{pkg}.{tcs_func_match_obj.group(1)}"
                        cases[tcs] = [[tcs, "ERROR", 0.0, error_trace, 0.0]]
                        tcs_time[tcs] = 0.0
    return cases, tcs_time


def get_fuzz_cases(cfgs):
    global total_count
    fail_count = 0
    global error_count
    skip_count = 0
    pass_count = 0
    fail_list = []
    global error_list
    for log in glob.glob(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log", "split_log", "*.log")):
        pkg = log[14:-7]
        tcs = None
        with open(log, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line_one in lines:
            rem = re.match(r".*Done \d+ runs in \d+ second", line_one)
            if rem:
                '''success'''
                total_count += 1
                pass_count += 1
                break
            elif 'Aborted (core dumped)' in line_one:
                total_count += 1
                fail_count += 1
                for line in lines:
                    if 'Start to run case file: ' in line:
                        fail_list.append(line.split('Start to run case file: ')[-1].split('************************'))
                break
        else:
            for line in lines:
                if 'Start to run case file: ' in line:
                    item = line.split('Start to run case file: ')[-1].split('************************')[0]
                    if not error_list.__contains__(item):
                        total_count += 1
                        error_count += 1
                        error_list.append(item)

    logger.info("*" * 50)
    logger.info("Test fuzz Summary")
    logger.info(f"Total  : {total_count}")
    logger.info(f"Passed : {pass_count}")
    logger.info(f"Failed : {fail_count}")
    logger.info(f"Error  : {error_count}")
    logger.info(f"Skipped: {skip_count}")
    logger.info(f"Ratio  : {round((pass_count + skip_count) / total_count * 100, 2) if total_count > 0 else 0}%")
    show_case_list(fail_list, "Failed")
    show_case_list(error_list, "Error")
    logger.info("*" * 50)
    logger.info("View the full log in log/all.log, or view the log of each case under log/split_log")
    if fail_count == 0 and error_count == 0:
        return 0
    else:
        return 1


def gen_junit_report(cfgs, cases, tcs_time):
    global total_count
    fail_count = 0
    global error_count
    skip_count = 0
    pass_count = 0
    fail_list = []
    global error_list
    skip_list = []
    testsuites = Et.Element("testsuites")
    tcs_info = {}  # {test_class:[total, passed, failed, error, skipped]}
    for tcs in cases.keys():
        class_name = tcs
        testsuite = Et.SubElement(testsuites, "testsuite", name=class_name,
                                  time=str(tcs_time[tcs] / 1000 / 1000 / 1000))
        tcs_info[tcs] = [0, 0, 0, 0, 0]
        for case in cases[tcs]:
            case_name, status, case_time_elapsed, error_trace, case_time_per_op = case
            testcase = Et.SubElement(testsuite, "testcase", class_name=class_name, name=case_name,
                                     time=str(case_time_elapsed / 1000 / 1000 / 1000))
            if "FAILED" in status:
                fail_info = Et.SubElement(testcase, "failure")
                fail_info.text = error_trace
                fail_count += 1
                tcs_info[tcs][2] += 1
                fail_list.append(f"{tcs}.{case_name}")
            elif "ERROR" in status:
                error_info = Et.SubElement(testcase, "error")
                error_info.text = error_trace
                error_count += 1
                tcs_info[tcs][3] += 1
                error_list.append(f"{tcs}.{case_name}")
            elif "SKIP" in status:
                Et.SubElement(testcase, "skipped")
                skip_count += 1
                tcs_info[tcs][4] += 1
                skip_list.append(f"{tcs}.{case_name}")
            else:
                pass_count += 1
                tcs_info[tcs][1] += 1
            total_count += 1
            tcs_info[tcs][0] += 1
        testsuite.set("tests", str(tcs_info[tcs][0]))
        testsuite.set("failures", str(tcs_info[tcs][2]))
        testsuite.set("errors", str(tcs_info[tcs][3]))
        testsuite.set("skipped", str(tcs_info[tcs][4]))
    testsuites.set("tests", str(total_count))
    testsuites.set("failures", str(fail_count))
    testsuites.set("errors", str(error_count))
    testsuites.set("skipped", str(skip_count))
    xml_str = Et.tostring(testsuites).decode()
    xml_str = re.sub(r'[^\x0A\x20-\x7e]', r'', xml_str)
    result_pretty = minidom.parseString(xml_str).toprettyxml(indent="    ")
    with open(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "report", "result.xml"), "w+", encoding='UTF-8') as f:
        f.write(result_pretty)

    logger.info("*" * 50)
    logger.info("Test Summary")
    logger.info(f"Total  : {total_count}")
    logger.info(f"Passed : {pass_count}")
    logger.info(f"Failed : {fail_count}")
    logger.info(f"Error  : {error_count}")
    logger.info(f"Skipped: {skip_count}")
    logger.info(f"Ratio  : {round((pass_count + skip_count) / total_count * 100, 2) if total_count > 0 else 0}%")

    show_case_list(fail_list, "Failed")
    show_case_list(error_list, "Error")
    show_case_list(skip_list, "Skipped")
    logger.info("*" * 50)
    logger.info("View the full log in log/all.log, or view the log of each case under log/split_log")
    if fail_count == 0 and error_count == 0:
        return 0
    else:
        return 1


def show_case_list(case_list, status):
    if len(case_list) > 0:
        logger.info("*" * 50)
        logger.info(f"{status} listed below:")
        for l in case_list:
            logger.info(l)


def gen_perf_csv(cases, cfgs):
    with open(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "report", "perf.csv"), "w+", encoding='UTF-8') as f:
        writer = csv.writer(f)
        writer.writerow(["class", "case_name", "status", "case_time_elapsed(ns)", "case_time_per_op(ns/op)"])
        for tcs in cases.keys():
            for case in cases[tcs]:
                case_name, status, case_time_elapsed, error_trace, case_time_per_op = case
                writer.writerow([tcs, case_name, status, case_time_elapsed, case_time_per_op])


def gen_report(args, cfgs):
    if args.fuzz:
        """"""
        return get_fuzz_cases(cfgs)
    else:
        cases, tcs_time = get_cases(cfgs)
        gen_perf_csv(cases, cfgs)
        is_succ = gen_junit_report(cfgs, cases, tcs_time)
        return is_succ


def HLTtest(args, cfgs):
    global _3rd_party_root
    global logger
    if cfgs.BUILD_TYPE == "ci_test" and os.path.exists(
            os.path.join(os.path.dirname(cfgs.HOME), "ci_bin", "libclang_rt.fuzzer_no_main.a")):
        fuzz_lib = os.path.join(os.path.dirname(cfgs.HOME), "ci_bin", "libclang_rt.fuzzer_no_main.a")
    if cp.get("test", "fuzz_lib") != "":
        fuzz_lib = cp.get("test", "fuzz_lib")
    _3rd_party_root = get_cjtest_path(args, cfgs, "")
    if _3rd_party_root == "":
        _3rd_party_root = Path(cfgs.HOME_DIR).parent
    logger = Logger(cfgs)
    if args.main:
        test_dir = 'benchmark'
    else:
        test_dir = 'HLT'
    cfgs.CJ_TEST_WORK = "test"
    if not os.path.exists(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, test_dir)):
        logger.error(f"{os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, test_dir)} test case not exists!")
        exit(1)
    run_options = cp.get("test", "run_options")
    compile_options = cp.get("test", "compile_options")
    target = "x86"
    if args.p:
        dirs = os.path.join(cfgs.HOME_DIR, args.p)
    else:
        dirs = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, test_dir)
    if args.target:
        target = args.target
        _3rd_party_root = get_cjtest_path(args, cfgs, args.target)
    elif args.main:
        os.environ['cjHeapSize'] = cp.get("test", "cjHeapSize")
        compile_options += ""
    elif args.fuzz:
        os.environ["CANGJIE_PATH"] = f"{fuzz_lib}:{os.getenv('CANGJIE_PATH')}"
        compile_options += f'--link-options="--whole-archive {fuzz_lib} -no-whole-archive -lstdc++ -lpthread" --sanitizer-coverage-inline-8bit-counters'
        fuzz_runs = cp.get("test", "fuzz_runs")
        fuzz_rss_limit_mb = cp.get("test", "fuzz_rss_limit_mb")
        if fuzz_runs:
            args.fuzz_runs = fuzz_runs
        else:
            args.fuzz_runs = 30000000
        if fuzz_rss_limit_mb:
            args.fuzz_rss_limit_mb = fuzz_rss_limit_mb
        else:
            args.fuzz_rss_limit_mb = 4096
        fuzz_dir = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "fuzz")
        if args.p and str(args.p).startswith(str(fuzz_dir)) and os.path.exists(args.p):
            cfgs.LOG.info(f"指定测试路径：{args.p}")
            dirs = args.p
        else:
            if os.path.exists(fuzz_dir):
                dirs = fuzz_dir
            elif os.path.exists(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "FUZZ")):
                dirs = os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "FUZZ")
            else:
                cfgs.LOG.error("当前仓库中没有test/fuzz目录, 请检查后再试.")
                exit(1)

    # else:
    #     run_options += f"{arg}"

    shutil.rmtree(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "tmp"), ignore_errors=True)
    shutil.rmtree(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "log"), ignore_errors=True)
    shutil.rmtree(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "report"), ignore_errors=True)
    os.makedirs(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "tmp"), exist_ok=True)
    os.makedirs(os.path.join(cfgs.HOME_DIR, cfgs.CJ_TEST_WORK, "report"), exist_ok=True)

    if cfgs.OS_PLATFORM and cfgs.OS_PLATFORM == "windows":
        copy_windows_lib(cfgs)
    if target == "ohos":
        cfgs.run_cmd(f"hdc shell rm -rf {ohos_dir};mkdir {ohos_dir};chmod -R 777 {ohos_dir}")
        if cfgs.BUILD_PARMS.get("target") is not None and cfgs.BUILD_PARMS["target"].get("aarch64-linux-ohos") \
                is not None and cfgs.BUILD_PARMS["target"]["aarch64-linux-ohos"].get("compile-option") is not None:
            cfgs.OHOS_CMD = str(cfgs.BUILD_PARMS["target"]["aarch64-linux-ohos"]["compile-option"])\
                .replace('${DEVECO_CANGJIE_HOME}', f'{os.environ["DEVECO_CANGJIE_HOME"]}').replace('\\', '/')
    cfgs.libs_3rd = []
    cfgs.import_cmd = set()
    cfgs.library_path_L_cmd = []
    cfgs.library_l_cmd = ""
    __find_cjpm_home_librarys(args, cfgs)
    for root, _, files in os.walk(dirs):
        for f in files:
            if f.endswith(".cj"):
                if args.case:
                    if args.case.endswith(".cj"):
                        if args.case == str(f):
                            run_one_case(args, os.path.join(root, f), run_options, compile_options, target, cfgs)
                    else:
                        if "{}.cj".format(args.case) == str(f):
                            run_one_case(args, os.path.join(root, f), run_options, compile_options, target, cfgs)
                else:
                    run_one_case(args, os.path.join(root, f), run_options, compile_options, target, cfgs)
    try:
        if args.HLT:
            gen_report(args, cfgs)
        else:
            exit(gen_report(args, cfgs))
    except AttributeError:
        exit(gen_report(args, cfgs))


