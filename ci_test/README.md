# 三方库使用脚本运行LLT/HLT测试用例

## 下载ci脚本

`git clone https://gitcode.com/Cangjie-TPC/TPC-Test-Framework.git`

可选两种方式使用ci脚本 本质上是一样的

1. 将`ci_tools/src/ci_test`配置到PATH环境变量 之后可使用`ciTest`命令
1. 使用`python ci_tools/src/main.py`命令

## 使用脚本编译三方库

1. 进入三方库根目录
1. 执行`ciTest build`命令
    1. 本质就是执行`cjpm build`命令

## 使用脚本运行LLT测试用例

1. 进入三方库根目录
1. 运行所有用例: 执行`ciTest test`命令
    1. 本质就是将test/LLT目录下的测试用例与三方库so联合编译生成可执行文件并执行
1. 运行某个单独的用例: `ciTest test --case test1`
    1. `test1.cj`是用例的名称
    1. 加不加后缀都可以识别
    1. 无需考虑目录层级 会扫描整个LLT目录树

## 使用脚本运行HLT测试用例

1. 进入三方库根目录
1. 运行所有用例: 执行`ciTest cjtest`命令
    1. 本质就是将test/HLT目录下的测试用例与三方库so联合编译生成可执行文件并执行
1. 运行某个单独的用例: `ciTest cjtest --case test1`
    1. `test1.cj`是HLT目录里用例的名称
    1. 加不加后缀都可以识别
    1. 无需考虑目录层级 会扫描整个HLT目录树

## tips

脚本的目的就是利用cangjie的包管理器和cjc编译器, 简化编译测试流程.

本质就是拷贝资源/拼接cjc编译命令/运行, 脚本运行时会打印使用的cjc编译命令.

如有更多需求, 仔细研究cjc编译命令选项, 本质都是一样的.
