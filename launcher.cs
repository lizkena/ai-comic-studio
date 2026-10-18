using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

public static class Launcher
{
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window, int command);

    [STAThread]
    public static void Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string identity;
        using (var hash = SHA256.Create())
            identity = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(root.ToUpperInvariant()))).Replace("-", "");
        using (var mutex = new Mutex(false, "Local\\AIComicStudio_" + identity))
        {
            bool acquired = false;
            try
            {
                try { acquired = mutex.WaitOne(0); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired)
                {
                    foreach (var process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(Application.ExecutablePath)))
                    {
                        try
                        {
                            if (process.MainModule.FileName.Equals(Application.ExecutablePath, StringComparison.OrdinalIgnoreCase))
                            {
                                ShowWindow(process.MainWindowHandle, 9);
                                SetForegroundWindow(process.MainWindowHandle);
                            }
                        }
                        catch { }
                        finally { process.Dispose(); }
                    }
                    return;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new StudioWindow(root, Array.IndexOf(args, "--verify-desktop") >= 0, Array.IndexOf(args, "--storyboard") >= 0 ? "storyboard" : Array.IndexOf(args, "--library") >= 0 ? "library" : Array.IndexOf(args, "--third-party") >= 0 ? "third-party" : Array.IndexOf(args, "--appearance") >= 0 ? "appearance" : Array.IndexOf(args, "--settings") >= 0 ? "api" : null));
            }
            catch (Exception ex) { MessageBox.Show(ex.Message, "AI漫剧工作台", MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally { if (acquired) mutex.ReleaseMutex(); }
        }
    }
}

internal sealed class StudioWindow : Form
{
    private readonly string root;
    private readonly string data;
    private readonly bool verify;
    private readonly bool openSettings;
    private readonly string settingsSection;
    private readonly Label loading;
    private readonly Button retry;
    private WebView2 view;
    private string origin;
    private bool initialized;
    private bool busy;
    private bool closingApproved;
    private bool verificationDone;
    private readonly JavaScriptSerializer json = new JavaScriptSerializer();
    [DllImport("dwmapi.dll")] private static extern int DwmSetWindowAttribute(IntPtr window, int attribute, ref int value, int size);

    public StudioWindow(string workspace, bool verification, string section)
    {
        root = workspace; data = Path.Combine(root, "data"); verify = verification; settingsSection = section; openSettings = section != null && section != "library" && section != "storyboard";
        Directory.CreateDirectory(data);
        Text = "AI漫剧工作台";
        BackColor = Color.FromArgb(19, 21, 26); ForeColor = Color.FromArgb(233, 236, 242);
        Font = new Font("Microsoft YaHei UI", 10);
        AutoScaleMode = AutoScaleMode.Dpi; StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(960, 640);
        var screen = Screen.FromPoint(Cursor.Position).WorkingArea;
        Size = new Size(Math.Min(1440, screen.Width), Math.Min(940, screen.Height));
        WindowState = FormWindowState.Maximized;
        string iconFile = Path.Combine(root, "studio.ico");
        Icon = File.Exists(iconFile) ? new Icon(iconFile) : Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        loading = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
            Text = "AI漫剧工作台\n\n正在启动本地工作台…", ForeColor = ForeColor, BackColor = BackColor };
        retry = new Button { Text = "重新连接", Dock = DockStyle.Bottom, Height = 48, Visible = false,
            FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(35, 38, 46), ForeColor = ForeColor };
        retry.Click += async (s, e) => await InitializeStudio();
        Controls.Add(loading); Controls.Add(retry);
        Shown += async (s, e) => await InitializeStudio();
        FormClosing += CheckBeforeClose;
        FormClosed += (s, e) => SaveState("closed", null);
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        try
        {
            int dark = 1, caption = 0x1A1513, text = 0xF2ECE9;
            DwmSetWindowAttribute(Handle, 20, ref dark, 4);
            DwmSetWindowAttribute(Handle, 35, ref caption, 4);
            DwmSetWindowAttribute(Handle, 36, ref text, 4);
        }
        catch { }
    }

    private static int StartBackend(string workspace)
    {
        var script = Path.Combine(workspace, "start.ps1");
        if (!File.Exists(script)) throw new FileNotFoundException("缺少 start.ps1，请保持工作台目录完整。");
        var info = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\" -BackendOnly") {
            WorkingDirectory = workspace, UseShellExecute = false, CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden, RedirectStandardOutput = true,
            RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        using (var process = new Process { StartInfo = info })
        {
            process.Start();
            var error = process.StandardError.ReadToEndAsync();
            var output = process.StandardOutput.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode != 0) throw new Exception("本地服务启动失败：\n" + error.Result + "\n详情见 data/startup-error.log。");
            foreach (var line in output.Split('\n'))
            {
                int port;
                if (line.Trim().StartsWith("STUDIO_PORT=") && int.TryParse(line.Trim().Substring(12), out port) && port >= 8766 && port <= 8786) return port;
            }
            throw new Exception("启动器没有返回本地服务地址，请检查 data/server-error.log。");
        }
    }

    private async Task InitializeStudio()
    {
        if (busy || IsDisposed) return;
        busy = true;
        loading.Text = "AI漫剧工作台\n\n正在启动本地工作台…";
        loading.Visible = true; loading.BringToFront(); retry.Visible = false;
        try
        {
            int port = await Task.Factory.StartNew(() => StartBackend(root));
            if (IsDisposed) return;
            origin = "http://127.0.0.1:" + port;
            if (!initialized)
            {
                CoreWebView2Environment.GetAvailableBrowserVersionString();
                if (view != null) view.Dispose();
                view = new WebView2 { Dock = DockStyle.Fill, DefaultBackgroundColor = BackColor, Visible = false };
                Controls.Add(view);
                var environment = await CoreWebView2Environment.CreateAsync(null, Path.Combine(data, "webview"));
                if (IsDisposed) return;
                await view.EnsureCoreWebView2Async(environment);
                view.CoreWebView2.Settings.IsStatusBarEnabled = false;
                view.CoreWebView2.Settings.IsZoomControlEnabled = false;
                view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                view.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled = false;
                view.CoreWebView2.NewWindowRequested += (s, e) => { e.Handled = true; OpenLinkedWindow(e.Uri); };
                view.CoreWebView2.DownloadStarting += (s, e) => SelectDownloadPath(this, e);
                view.CoreWebView2.NavigationStarting += (s, e) => {
                    if (e.Uri.StartsWith(origin + "/", StringComparison.OrdinalIgnoreCase) || e.Uri == origin) return;
                    e.Cancel = true;
                    if (e.IsUserInitiated) OpenLinkedWindow(e.Uri);
                };
                view.CoreWebView2.NavigationCompleted += NavigationReady;
                view.CoreWebView2.ProcessFailed += (s, e) => { initialized = false; ShowFailure("界面进程意外退出，请点击重新连接。"); };
                initialized = true;
            }
            SaveState("loading", null);
            view.CoreWebView2.Navigate(origin + "/?launch=" + DateTime.UtcNow.Ticks + (settingsSection == "storyboard" ? "&page=project&view=storyboard" : settingsSection == "library" ? "&page=library" : openSettings ? "&page=settings&section=" + (settingsSection == "third-party" ? "api&channel=custom" : settingsSection) : ""));
        }
        catch (WebView2RuntimeNotFoundException) { ShowFailure("缺少 Microsoft WebView2 Runtime。请安装运行时后重新打开工作台。\n下载地址：developer.microsoft.com/microsoft-edge/webview2"); }
        catch (Exception ex) { ShowFailure(ex.Message); }
        finally { busy = false; }
    }

    private async void NavigationReady(object sender, CoreWebView2NavigationCompletedEventArgs e)
    {
        if (IsDisposed) return;
        // Switching a navigation to a file download can abort that navigation.
        // Keep the already loaded workbench visible instead of hiding it.
        if (!e.IsSuccess && view != null && view.Visible &&
            (e.WebErrorStatus == CoreWebView2WebErrorStatus.ConnectionAborted ||
             e.WebErrorStatus == CoreWebView2WebErrorStatus.OperationCanceled)) return;
        if (!e.IsSuccess) { ShowFailure("界面连接失败：" + e.WebErrorStatus + "。请点击重新连接。"); return; }
        loading.Visible = false; retry.Visible = false; view.Visible = true; view.BringToFront(); view.Focus();
        SaveState("ready", null);
        if (verify && !verificationDone)
        {
            verificationDone = true;
            try
            {
                string evidence = null;
                for (int i = 0; i < 40; i++)
                {
                    await Task.Delay(250);
                    if (IsDisposed) return;
                    evidence = await view.CoreWebView2.ExecuteScriptAsync("JSON.stringify({title:document.title,url:location.href,heading:document.querySelector('h1')?.innerText||'',body:document.body.innerText.slice(0,6000),platformList:!!document.querySelector('.platform-rail'),modelPicker:!!document.querySelector('#platform-model-picker'),width:innerWidth,height:innerHeight,buttons:document.querySelectorAll('button').length})");
                    if (settingsSection == "storyboard" ? evidence.Contains("分镜设计") && evidence.Contains("创作助手") : settingsSection == "library" ? evidence.Contains("管理素材") && evidence.Contains("新建资产") : settingsSection == "appearance" ? evidence.Contains("日间模式") && evidence.Contains("跟随系统") : openSettings ? evidence.Contains("测试连接") && evidence.Contains("保存渠道") : evidence.Contains("新建作品")) break;
                }
                string path = Path.Combine(root, "docs", settingsSection == "storyboard" ? "独立窗口-分镜工作区验证.png" : settingsSection == "library" ? "独立窗口-资产库验证.png" : settingsSection == "third-party" ? "独立窗口-第三方渠道验证.png" : settingsSection == "appearance" ? "独立窗口-设置布局验证.png" : openSettings ? "独立窗口-API设置验证.png" : "独立窗口内容.png");
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using (var stream = File.Create(path)) await view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream);
                SaveState("verified", json.Deserialize<string>(evidence));
            }
            catch (Exception ex) { SaveState("verification-error", ex.Message); }
        }
    }

    private async void OpenLinkedWindow(string address)
    {
        Uri uri;
        if (!Uri.TryCreate(address, UriKind.Absolute, out uri) || (uri.Scheme != "http" && uri.Scheme != "https")) return;
        var popup = new Form { Text = "AI漫剧工作台 · " + (uri.GetLeftPart(UriPartial.Authority) == origin ? "素材预览" : "参考与工具"),
            BackColor = BackColor, StartPosition = FormStartPosition.CenterParent, Size = Size,
            Icon = Icon, AutoScaleMode = AutoScaleMode.Dpi };
        var browser = new WebView2 { Dock = DockStyle.Fill, DefaultBackgroundColor = BackColor };
        popup.Controls.Add(browser);
        popup.Show(this);
        try
        {
            await browser.EnsureCoreWebView2Async(view.CoreWebView2.Environment);
            if (popup.IsDisposed) return;
            browser.CoreWebView2.Settings.IsStatusBarEnabled = false;
            browser.CoreWebView2.NewWindowRequested += (s, e) => { e.Handled = true; OpenLinkedWindow(e.Uri); };
            browser.CoreWebView2.DownloadStarting += (s, e) => SelectDownloadPath(popup, e);
            browser.CoreWebView2.Navigate(uri.AbsoluteUri);
        }
        catch (Exception ex)
        {
            if (!popup.IsDisposed) { MessageBox.Show(popup, ex.Message, "打开链接失败"); popup.Close(); }
        }
    }

    private static void SelectDownloadPath(Form owner, CoreWebView2DownloadStartingEventArgs e)
    {
        e.Handled = true;
        var deferral = e.GetDeferral();
        // Leave the WebView event before displaying a modal native dialog.
        // Only the studio's save dialog owns the download destination.
        try
        {
            owner.BeginInvoke(new MethodInvoker(() => {
                try
                {
                    if (owner.IsDisposed) { e.Cancel = true; return; }
                    string directory = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "data", "exports");
                    Directory.CreateDirectory(directory);
                    using (var dialog = new SaveFileDialog { Title = "保存工作台导出文件", FileName = Path.GetFileName(e.ResultFilePath),
                        InitialDirectory = directory, OverwritePrompt = true, CheckPathExists = true, RestoreDirectory = true })
                    {
                        if (dialog.ShowDialog(owner) == DialogResult.OK) e.ResultFilePath = dialog.FileName;
                        else e.Cancel = true;
                    }
                }
                catch (Exception ex)
                {
                    e.Cancel = true;
                    if (!owner.IsDisposed) MessageBox.Show(owner, "无法保存下载文件，请选择可写入的文件夹。\n" + ex.Message,
                        "保存文件", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
                finally { deferral.Complete(); deferral.Dispose(); }
            }));
        }
        catch { e.Cancel = true; deferral.Complete(); deferral.Dispose(); throw; }
    }

    private void ShowFailure(string message)
    {
        if (IsDisposed) return;
        loading.Text = "AI漫剧工作台\n\n" + message;
        loading.Visible = true; loading.BringToFront(); retry.Visible = true; retry.BringToFront();
        SaveState("error", message);
    }

    private void SaveState(string status, string evidence)
    {
        try
        {
            File.WriteAllText(Path.Combine(data, "desktop-state.json"), json.Serialize(new {
                pid = Process.GetCurrentProcess().Id, title = Text, status = status, url = origin,
                host = "WinForms-WebView2", workspace = root, evidence = evidence, utc = DateTime.UtcNow.ToString("o")
            }), new UTF8Encoding(false));
        }
        catch { }
    }

    private async void CheckBeforeClose(object sender, FormClosingEventArgs e)
    {
        if (closingApproved || !initialized || view == null || view.CoreWebView2 == null) return;
        e.Cancel = true;
        try
        {
            string dirty = await view.CoreWebView2.ExecuteScriptAsync("(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented})()");
            if (dirty == "true" && MessageBox.Show(this, "还有未保存的修改。要关闭工作台窗口吗？", "AI漫剧工作台", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
        }
        catch { }
        closingApproved = true; Close();
    }
}
