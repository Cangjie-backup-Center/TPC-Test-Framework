# TPC-Test-Framework

纯仓颉项目LLT和HLT用例执行脚本

## 脚本执行环境限制

- 脚本支持的python版本 `3.8.*`-`3.10.*`

### 使用脚本前, 需要了解 Cangjie 编译流程和编译命令执行. 

- `cjpm` 编译 请见 [链接](https://cangjie-lang.cn/docs?url=%2F1.0.3%2Fuser_manual%2Fsource_zh_cn%2Fcompile_and_build%2Fcjpm_usage_OHOS.html)
- `cjc` 编译 请见 [链接](https://cangjie-lang.cn/docs?url=%2F1.0.3%2Fuser_manual%2Fsource_zh_cn%2Fcompile_and_build%2Fcjc_usage.html)

### main.py 调用

- 需要保持目录解构

```cmd
├── ci_test         当前ci_test复制到这个位置
├── src             测试项目的原码目录
└── cjpm.toml       测试项目的配置文件
``` 
    
- 调用时使用`pyhton3 ./ci_test/main.py [option] ...`

### ciTest.py 命令调用

- 需要将[ciTest.py](./ci_test/ciTest.py) 设置到环境变量. 
    - windows 环境 需要将[ciTest.py](./ci_test/ciTest.py)的路径设置到 `高级环境变量设置`的`PATH`中
    - linux 环境 需要将[ciTest.py](./ci_test/ciTest.py)的路径设置到`PATH`中
- windows调用时使用`pyhton3 ciTest.py [option] ...`
- linux调用时使用`ciTest.py [option] ...`

### main.py 和 ciTest.py 调用方式区别

#### 执行目录要求不同

- main.py 方式 必须将`ci_test`放在和`src`文件夹同级. 执行时需要在 `cjpm.toml` 同级目录中执行
- ciTest.py 方式, 无需考虑目录存放位置, 但必须设置在 `PATH` 环境变量里, 执行时需要在 cjpm.toml同级目录中执行

#### 环境变量设置不同

- main.py 无需设置环境变量. 
- ciTest.py `必须`设置到 `PATH` 环境变量中

### 支持纯仓颉项目编译

#### 普通编译
```shell
ciTest.py build --cj-home=cjc环境目录 # 第一次编译会提醒， 之后可以直接使用 ciTest.py build
```

#### 覆盖率统计时编译
```shell
ciTest.py build --coverage
```

### 支持LLT测试

#### LLT用例特殊标识

- `// EXEC:` 执行命令
- `// DEPENDENCE`  依赖测试文件相对路径
- `// RESOURCES`  依赖测试文件绝对路径， 项目/test/resources

例如: 请查看 [LLT用例](https://gitcode.com/Cangjie-TPC/io4cj/blob/develop/test/LLT/bug_I5TM9F.cj)

#### 测试命令
```shell
ciTest.py llt
```
#### 覆盖率测试命令, 前提编译时带有 `coverage` 才生效
```shell
ciTest.py llt --coverage
```
#### 单跑一条LLT用例测试命令(匹配用例名)
```shell
ciTest.py llt --case=xx.cj  # .cj 可以省略
```

#### 指定测试目录跑
```shell
ciTest.py llt --path=./test/LLT/abc
```

### 支持HLT测试(cjtest命令)

#### HLT用例特殊标识
- `// 3rd_party_lib:三方库目录1:三方库目录2`：标记依赖的三方库so所在目录，与`conf.cfg`文件中`3rd_party_root`字段配合使用组合成绝对路径。多个三方库目录用`:`分隔，或添加多行`// 3rd_party_lib:`
- `// macro-lib:marco1.so:marco2.so`：标记依赖的宏定义的动态库文件，与`conf.cfg`文件中`3rd_party_root`字段配合使用组合成绝对路径。多个宏动态库文件用`:`分隔，或添加多行`// marco-lib:`
- `// data_file:数据文件1:数据文件2`：当用例中需要读取其他数据文件时添加，需为测试脚本所在相对目录。多个数据文件用`:`分隔，或添加多行`// data_file:`
- `// run_option:选项1 选项2`：当用例运需要增加特殊运行时选项时添加，多个选项用`:`或`空格`分隔，或使用多行`// run_option:`
- `// dependence:文件a 文件b`：当用例依赖其他cj文件时添加，使用相对于用例的相对路径，多个文件用`:`或`空格`分隔，或使用多行`// dependence:`
- `// source_file:文件a 文件b`：绝对路径数据文件1:绝对路径数据文件2`：当用例中需要读取其他数据文件时添加，需为测试脚本所在相对目录。多个数据文件用`:`分隔，或添加多行`// source_file:`

例如: 请查看 [HLT用例](https://gitcode.com/Cangjie-TPC/io4cj/blob/develop/test/HLT/buffer/test_buffer_combination.cj)

#### 测试命令
```shell
ciTest.py hlt
```
#### 覆盖率测试命令
```shell
ciTest.py hlt --coverage
```

#### 单跑一条LLT用例测试命令(匹配用例名)
```shell
ciTest.py hlt --case=xx.cj  # .cj 可以省略
```

#### 指定测试目录
```shell
ciTest.py hlt -p=./test/HLT/abc
```

### 支持benchmark测试
#### 测试命令
```shell
ciTest.py bench -p ./test/bench
```
#### 测试命令 在cjtest仓库时
```shell
ciTest.py bench -p ./test/bench --cjc=0.39.7
```

### 支持覆盖率直接生成
```shell
ciTest.py coverage
```

### 若仓颉版本0.60.*以上时需要注意stdx文件夹配置 

- 注意: 以linux x86_64环境为例, 将cangjie-stdx-linux-x64-0.60.5.1.zip解压仓颉环境目录下linux_x86_64_llvm
- 若未下载 stdx 环境, 脚本会自动为您在仓颉环境中下载stdx依赖包.

#### 仓颉环境已经配置情况下, 需要配置stdx文件夹路径. 

```
// 已经设置好的Cangjie环境目录, 注意stdx包解压的位置
├── bin
├── envsetup.sh
├── lib
├── modules
├── README.md
├── runtime
├── linux_x86_64_llvm    // linux_x86_64_llvm 文件夹放在这里即可
├── third_party
└── tools
```

### 开源协议
Apache License Version 2.0

### 参与贡献

欢迎给我们提交PR，欢迎给我们提交Issue，欢迎参与任何形式的贡献。
