```
[test-home]
dir = ../../test

[running]
temp_dir = ../test_temp/run

[logging]
name = ../test_temp/log
level = INFO

[test]
3rd_party_root = HLT测试需要设置的项目根目录, 如果不设置的则为当前执行脚本的目录
3rd_party_root_ohos = 
fuzz_lib = 
fuzz_runs = 
fuzz_rss_limit_mb = 
compile_options = --test -Woff unused HLT 编译时需要新增的编译选项
run_options = 
CJHEAPSIZE = 1GB

[cangjie-home]
OHOS_compile_option = 
DEVECO_CANGJIE_HOME = 
OHOS_ROOT = 
OHOS_version = 
home = 仓颉环境目录
cjpm =  cjpm 管理的git目录
update_toml = false 是否修改cjpm.toml文件

[build-warning]
warning = 0
```
