# 修改host文件使用github
1、windows电脑打开 `C:\Windows\System32\drivers\etc` 路径找到hosts文件

![](../assets/2026-09-19-20-45-10.png)

2、通过dns查询工具查找 `github.com` 的dns服务器ip

![](../assets/2026-09-19-20-53-48.png)

3、在hosts文件末尾添加 `github.com` 的ip和域名，并保存

![](../assets/2026-09-19-20-54-49.png)

4、打开cmd，输入 `ipconfig/flushdns` 刷新本地dns即可完成

![](../assets/2026-09-19-20-56-49.png)