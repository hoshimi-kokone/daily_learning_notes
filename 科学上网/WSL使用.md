```bash
wsl                      :: 进入 Ubuntu
exit                     :: 退出（Ctrl+D 同效）
wsl -l -v                :: 看发行版和状态
wsl --shutdown           :: 彻底关闭 WSL 虚拟机
\\wsl.localhost\Ubuntu   :: 在资源管理器里看 Linux 文件
```

## 一、启动与退出

**进入** (三种方式任选)：

- 在任意 cmd / PowerShell / Windows Terminal 里输入 `wsl`
- 开始菜单点 **Ubuntu**
- `Win + R` -> 输入 `wsl`

**退出**：

`exit` 或 `Ctrl + D`

**重要区别**：关掉终端窗口 **不等于** 关掉Linux。WSL2 的虚拟机会在后台继续运行，你的进程 (比如 `npm run dev`) 也还在跑。真正全部停止要用：

```bash
wsl --shutdown
```

用 `wsl -l -v` 看 `STATE` : `Running` 表示还在跑，`Stopped` 表示已关。

**从 Windows 直接跑 Linux 命令** (不用先进交互式 shell)：

```bash
wsl ls -la
wsl -d Ubuntu -- python3 --version
wsl -u root                    :: 以 root 进
```

## 二、文件在哪里 (新手最常卡的点)

| 方向 | 怎么访问 |
|---|---|
| Windows -> Linux | 资源管理器地址栏输入 `\\wsl.localhost\Ubuntu`，或直接在 Ubuntu 里敲 `explorer.exe .` |
| Linux -> Windows | `/mnt/c/`、`/mnt.d/` (你的D盘就是 `/mnt/d`) |
| Ubuntu 系统的“硬盘” | `D:\WSL\Ubuntu\ext4.vhdx`，**别碰这个文件** |

**性能铁律**：项目放在 Linux 侧 (`/home/hoshimi_kokone/...`)，不要放在 `/mnt/d`。

```bash
# 好：Linux 原生文件系统
cd ~ && git clone <仓库>

# 差：跨文件系统，I/O 慢 5~10 倍
cd /mnt/d/codes/xxx
```

原因：`/mnt/d` 是通过 9p/drvfs 协议转发到 NTFS，每次文件操作都有协议开销。`npm install`、编译这类大量小文件操作时差距极其明显。

**权限坑**：`/mnt/d` 下的文件在 Linux 里一律显式为 777，`git` 会误判权限变化：

```bash
git config --global core.fileMode false
```

## 三、Ubuntu 里装软件

```bash
sudo apt update            # 刷新软件列表
sudo apt upgrade -y        # 升级已装软件
sudo apt install -y git curl wget unzip build-essential
```

`sudo` 密码就是装系统时舍得那个 (输入时不显示字符)

**建议一开始就装的基础包**：

```bash
sudo apt install -y build-essential git curl wget unzip python3 python3-pip
```

> 如果 `apt` 下载很慢，说明在连海外源。换成国内镜像能快一个数量级 —— 告诉我你的 Ubuntu 版本 (`lsb_telease -a`)，我给你对应的换源命令

**更新 WSL 本体** (和 Ubuntu 无关，是 Windows 侧的东西)：

```bash
wsl --update
```

## 四、和 Windows 互通 (这是 WSL 最实用的部分)

**端口自动互通**：在 Ubuntu 里起个服务，Windows 浏览器直接访问 `localhost` 就行：

```bash
python3 -m http.server 8000
```

然后在 Windows 浏览器打开 `http://localhost:8080` —— 能开。前端开发、本地 API 调试全靠这个。

**在 Linux 里调用 Windows 程序**：

```bash
notepad.exe 文件.txt        # 用 Windows 记事本打开
explorer.exe .              # 用资源管理器打开当前目录
clip.exe < 文件             # 把内容复制到 Windows 剪贴板
powershell.exe -c "Get-Date"
```

**剪切板**：Windows Terminal 里 `Ctrl + Shift + C` / `Ctrl + Shift + V` ，或直接右键

**GUI 程序**：WSLg已内置，装个图形软件能直接弹窗，不需要 X Server：

```bash
sudo apt install -y x11-apps && xeyes
```

## 五、写代码：VS Code 的正确姿势

1. Windows 侧装 VS Code 和 **WSL 扩展** (Remote - WSL)
2. 在 Ubuntu 里进到项目目录，敲：

```bash
code .
```

它会自动用 Windows 的 VS Code 连进来，终端、调试、扩展全部在 Linux 环境里跑，但界面是原生 Windows 窗口。这是 WSL 开发体验最好的方式。

**不要** 用 Windows 版编辑器直接打开 `\\wsl.localhost\Ubuntu\...` 里的文件做 Git 操作 —— 路径和换行符容易出问题。

## 六、两个配置文件，别搞混

| 文件 | 位置 | 管什么 |
|---|---|---|
| `.wslconfig` | `C:\User\lenovo\.wslconfig` | **全局**：内存上限、CPU、swap、网络模式 |
| `wsl.conf` | Ubuntu 内 `/etc/wsl.conf` | **单个发行版**：默认用户、automount、systemd、开机命令 |

你已经有 `.wslconfig` 了。如果以后发现 Ubuntu 里 `systemctl` 不能用，就往 `/etc/wsl.conf` 加：

```ini
[boot]
systemd=true
```

然后 `wsl --shutdown` 重启生效

## 七、几个必踩的坑，提前知道

1. **换行符 (CRLF)** —— Git 拉下来的脚本报 `bad interpreter: /bin/bash^M`
```bash
git config --global core.autocrlf input
```
2. **大小写敏感** —— Linux 区分 `READ.md` 和 `read.md` ，从 Windows 拷过来的项目可能出问题。
3. **别再 `/mnt/*` 下执行 `chmod` / `chown`** —— NTFS 不支持 POSIX 权限，命令会 “成功” 但毫无效果
4. `wsl --shutdown` **会杀掉正在跑的服务** —— 别再跑着数据库或 dev server 的时候随手执行
5. **磁盘只增不减** —— 就是上一轮讲的 `ext4.vhdx` ，需要时用 `wsl --manage Ubuntu --set-sparse true` 压缩

## 八、日常维护命令速查

```text
wsl -l -v                      :: 列表 + 状态 + 版本
wsl --status                   :: 全局状态
wsl -d Ubuntu                  :: 进指定发行版
wsl --terminate Ubuntu         :: 只关这一个（下次自动重启）
wsl --shutdown                 :: 全关
wsl --update                   :: 更新 WSL 本体
wsl --export Ubuntu D:\WSL\bak.tar    :: 备份
wsl -l -o                      :: 看可安装的其他发行版
```

## 九、想装 Docker 的话

两条路：

1. **Docker Desktop** (Windows 侧装，勾选 WSL 集成) —— 图形界面友好，但要注意商业授权
2. **在 Ubuntu 里装 Docker Engine` —— 更轻，纯命令行：
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER    # 免 sudo 用 docker，需要重新登录
```

考虑到你之前在折腾 VMware 和虚拟机，如果主要目的是跑 SQL Server / Redis / 各种服务，第 2 条路更适合你。