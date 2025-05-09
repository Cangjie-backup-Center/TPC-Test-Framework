# TPC-Test-Framework

仓颉LLT和HLT用例执行脚本

## 1.两种方式调用测试脚本,：
### 1.1 脚本支持的python版本 `3.8.*`-`3.10.*`
### 1.2 main.py 调用

- 需要保持目录解构
```cmd
├── ci_test         当前ci_test复制到这个位置
├── src             测试项目的原码目录
└── cjpm.toml       测试项目的配置文件
``` 
    
- 调用时使用`pyhton3 ./ci_test/main.py [option] ...`

### 1.3 ciTest 命令调用

- 需要将[ciTest](./ci_test/ciTest) 设置到环境变量. 
    - windows 环境 需要将[ciTest](./ci_test/ciTest)的路径设置到 `高级环境变量设置`的`PATH`中
    - linux 环境 需要将[ciTest](./ci_test/ciTest)的路径设置到`PATH`中
- windows调用时使用`pyhton3 ciTest.py [option] ...`
- linux调用时使用`ciTest [option] ...`

### 2 支持编译

#### 2.1 普通编译
```shell
ciTest build --cj-home=cjc环境目录 # 第一次编译会提醒， 之后可以直接使用 ciTest build
```

#### 2.2 覆盖率统计时编译
```shell
ciTest build --coverage
```

### 3 支持LLT测试(test命令)

#### 3.1 LLT用例特殊标识

    * `// EXEC:` 执行命令
    * `// DEPENDENCE`  依赖测试文件相对路径
    * `// RESOURCES`  依赖测试文件绝对路径， 项目/test/resources

#### 3.2 测试命令
```shell
ciTest test
```

#### 3.3 覆盖率测试命令
```shell
ciTest test --coverage
```

#### 3.4 单跑一条LLT用例测试命令(匹配用例名)
```shell
ciTest test --case=xx.cj  # .cj 可以省略
```

#### 3.5 指定测试目录跑
```shell
ciTest test --path=./test/LLT/abc
```

### 4 支持HLT测试(cjtest命令)

#### 4.1 HLT用例特殊标识
    * `// 3rd_party_lib:三方库目录1:三方库目录2`：标记依赖的三方库so所在目录，与`conf.cfg`文件中`3rd_party_root`字段配合使用组合成绝对路径。多个三方库目录用`:`分隔，或添加多行`// 3rd_party_lib:`
    * `// macro-lib:marco1.so:marco2.so`：标记依赖的宏定义的动态库文件，与`conf.cfg`文件中`3rd_party_root`字段配合使用组合成绝对路径。多个宏动态库文件用`:`分隔，或添加多行`// marco-lib:`
    * `// data_file:数据文件1:数据文件2`：当用例中需要读取其他数据文件时添加，需为测试脚本所在相对目录。多个数据文件用`:`分隔，或添加多行`// data_file:`
    * `// run_option:选项1 选项2`：当用例运需要增加特殊运行时选项时添加，多个选项用`:`或`空格`分隔，或使用多行`// run_option:`
    * `// dependence:文件a 文件b`：当用例依赖其他cj文件时添加，使用相对于用例的相对路径，多个文件用`:`或`空格`分隔，或使用多行`// dependence:`
    * `// source_file:文件a 文件b`：绝对路径数据文件1:绝对路径数据文件2`：当用例中需要读取其他数据文件时添加，需为测试脚本所在相对目录。多个数据文件用`:`分隔，或添加多行`// source_file:`
#### 4.2 测试命令
```shell
ciTest cjtest
```
#### 4.3 覆盖率测试命令
```shell
ciTest cjtest --coverage
```

#### 4.4 单跑一条LLT用例测试命令(匹配用例名)
```shell
ciTest cjtest --case=xx.cj  # .cj 可以省略
```

#### 4.5 指定测试目录
```shell
ciTest cjtest -p=./test/HLT/abc
```

### 5 支持fuzz测试 在/test/fuzz目录
#### 5.1 测试命令
```shell
ciTest fuzz
```
#### 5.2 测试命令 指定目录
```shell
ciTest fuzz -p=./test/fuzz/abc
```

#### 5.3 测试命令 指定目录
```shell
ciTest fuzz --case=xx.cj   # .cj 可以省略
```

### 6 支持benchmark测试
#### 6.1 测试命令
```shell
ciTest bench -p ./test/bench
```
#### 6.2 测试命令 在cjtest仓库时
```shell
ciTest bench -p ./test/bench --cjc=0.39.7
```

### 7 支持覆盖率直接生成
```shell
ciTest coverage
```

### 8 若仓颉版本0.60.*以上时需要注意stdx文件夹配置 
**注意: 将解压后的文件夹名linux_x86_64_llvm 更改为 stdx** 
#### 8.1 仓颉环境已经配置情况下, 需要配置stdx文件夹路径. 
```commandline
// 已经设置好的Cangjie环境目录, 注意stdx文件夹的位置
├── bin
├── envsetup.sh
├── lib
├── modules
├── README.md
├── runtime
├── stdx    // stdx 文件夹放在这里即可
├── third_party
└── tools
```

#### 8.2 仓颉环境未配置情况下, 交给ci_test脚本读取, 各个仓颉版本需要按照版本号文件夹保存, 注意stdx文件夹的位置

ci_test/ci_test.cfg文件配置 home = /home/lyq/cangjie_env

```commandline
// cangjie_env的文件路径为 /home/xxx/cangjie_env(举例)
├── cangjie_env
│   ├── 0.56.4
│   ├── 0.57.3
│   ├── 0.58.3
│   ├── 0.59.6
│   ├── 0.60.5
│   └── stdx    // stdx 文件夹放在这里即可
│       └── 0.60.5   // 这里 是0.60.5版本的stdx目录

```

### 9 开源协议
Apache License Version 2.0

### 10 参与贡献

欢迎给我们提交PR，欢迎给我们提交Issue，欢迎参与任何形式的贡献。
