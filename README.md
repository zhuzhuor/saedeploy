# saedeploy

命令行部署程序或网站到 Sina App Engine

* 不需要学习 SVN，方便使用其它任意的版本控制系统
* 可以使用临时文件夹缓存文件，方便自动化部署
* SVN 服务器网络连接出错时，程序会自动重试
* 支持使用 `.saedeploy` 文件设置部署选项

## 安装方法

### 自动安装

    pip install saedeploy

或者

	easy_install saedeploy

### 手动安装

手动下载源码，之后运行

    python setup.py install


## 运行选项

	usage: saedeploy [-h] [-u USERNAME] [-p PASSWORD] [-v] [--trust-cert]
	                 [--local-cache] [--ignore IGNORE]
	                 [path]

	positional arguments:
	  path                  the folder containing config.yaml, which is the
	                        current folder by default

	optional arguments:
	  -h, --help            show this help message and exit
	  -u USERNAME, --username USERNAME
	  -p PASSWORD, --password PASSWORD
	  -v, --verbose
	  --trust-cert          always trust the SAE SVN server's TLS certificate
	  --local-cache         cache remote files locally to speed up deployment
	  --ignore IGNORE       files or folders to be ignored, separated by commas,
	                        such as --ignore=tmp,log,test

* `path` 用于指定 SAE 程序或网站的根目录，此目录下应包含有 SAE 的配置文件 `config.yaml` <br>如果不明确指定 `path`，程序会默认使用当前的目录作为程序或网站的根目录
* `-u/--username` 和 `-p/--password` 用来指定 SAE SVN 的用户名和密码
* `-v/--verbose` 使程序输出详细的操作日志
* `--trust-cert` 自动接受 SAE SVN 服务器的 TLS/SSL 证书
* `--local-cache` 使用 `~/.saedeploy` 文件夹来缓存 SAE 服务器上的文件，提高之后的部署速度<br>不使用这个选项时，程序会使用随机的文件目录来缓存文件，部署完成时会将此文件夹删除
* `--ignore` 用于指定需要忽略的文件或者文件夹，文件名之间用逗号隔开，例如 `--ignore log,tmp`

### 更多选项

* 除了 `path` 以外的选项及参数都可以从根目录里的 `.saedeploy` 文件中获取，但命令行参数具有更高的优先级
* 若命令行和配置文件中均没有提供 SVN 的用户名或密码，程序会尝试从环境变量`SAEDEPLOY_USERNAME` 及 `SAEDEPLOY_PASSWORD`中获取。这个方法可以避免隐私信息随着日志或者配置文件泄露

### 使用范例

	saedeploy --trust-cert --ignore log,tmp --username myusername@gmail.com --password mypassword my_app_folder


## License