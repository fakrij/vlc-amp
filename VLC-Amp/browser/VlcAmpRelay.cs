// VlcAmpRelay.cs - the local relay of "open links from the browser" on Windows (compiled by vlc-amp-url.ps1 with
// Add-Type: C# 5, .NET Framework 4). Same protocol as the relay in vlc-amp-url.py (Linux):
//
//   GET http://127.0.0.1:48081/<secret>/s?u=<https stream URL>&ua=<User-Agent>&ref=<Referer>
//   GET http://127.0.0.1:48081/<secret>/ping
//
// VLC asks for "the rest of the file" (no Range, or "bytes=N-"); YouTube answers such a request with HTTP 403 and
// only serves closed ranges. The relay fetches the stream in 10 MB ranges and passes them on as one response, so
// VLC can play and seek it. One connection = one response (Connection: close). Exits after 6 h without requests.
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

public static class VlcAmpRelay
{
    const long Chunk = 10L * 1024 * 1024;
    static string secret;
    static string logPath;
    static int active;
    static DateTime last = DateTime.UtcNow;
    static readonly object logLock = new object();

    public static void Log(string text)
    {
        if (logPath == null) return;
        lock (logLock)
        {
            try { File.AppendAllText(logPath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  relay: " + text + "\r\n"); }
            catch (IOException) { }
        }
    }

    // Blocks until the relay has been idle for idleHours. Returns false when the port is taken.
    public static bool Run(int port, string relaySecret, double idleHours, string log)
    {
        secret = relaySecret;
        logPath = log;
        ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
        ServicePointManager.DefaultConnectionLimit = 32;   // video + audio + seeks on one host (default is 2)
        TcpListener listener = new TcpListener(IPAddress.Loopback, port);
        try { listener.Start(); }
        catch (SocketException e) { Log("cannot listen on " + port + ": " + e.Message); return false; }
        Log("started (port " + port + ")");
        while (true)
        {
            if (listener.Pending())
            {
                TcpClient c = listener.AcceptTcpClient();
                Interlocked.Increment(ref active);
                last = DateTime.UtcNow;
                Thread t = new Thread(Serve);
                t.IsBackground = true;
                t.Start(c);
                continue;
            }
            if (Thread.VolatileRead(ref active) == 0 && (DateTime.UtcNow - last).TotalHours > idleHours) break;
            Thread.Sleep(50);
        }
        listener.Stop();
        Log("idle, exiting");
        return true;
    }

    static void Serve(object o)
    {
        TcpClient client = (TcpClient)o;
        try
        {
            client.NoDelay = true;
            NetworkStream ns = client.GetStream();
            ns.ReadTimeout = 15000;
            string head = ReadHead(ns);
            if (head != null) Handle(head, ns);
        }
        catch (IOException) { }               // VLC closed the connection (seek, stop)
        catch (SocketException) { }
        catch (ObjectDisposedException) { }
        catch (Exception e) { Log(e.GetType().Name + ": " + e.Message); }
        finally
        {
            try { client.Close(); } catch (Exception) { }
            last = DateTime.UtcNow;
            Interlocked.Decrement(ref active);
        }
    }

    // The request line and headers (up to the blank line), or null.
    static string ReadHead(Stream s)
    {
        StringBuilder sb = new StringBuilder();
        int b;
        while (sb.Length < 16384 && (b = s.ReadByte()) >= 0)
        {
            sb.Append((char)b);
            if (sb.Length >= 4 && sb[sb.Length - 1] == '\n' && sb.ToString(sb.Length - 4, 4) == "\r\n\r\n") return sb.ToString();
        }
        return null;
    }

    static void Reply(Stream s, string status, bool body)
    {
        byte[] data = Encoding.ASCII.GetBytes(body && status.StartsWith("200") ? "ok" : "");
        WriteHead(s, status, "Content-Length: " + data.Length + "\r\n");
        s.Write(data, 0, data.Length);
    }

    static void WriteHead(Stream s, string status, string headers)
    {
        byte[] h = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + "\r\n" + headers + "Connection: close\r\n\r\n");
        s.Write(h, 0, h.Length);
    }

    static string Query(string query, string key)
    {
        foreach (string part in query.Split('&'))
        {
            int eq = part.IndexOf('=');
            if (eq > 0 && part.Substring(0, eq) == key) return Uri.UnescapeDataString(part.Substring(eq + 1).Replace('+', ' '));
        }
        return "";
    }

    static HttpWebResponse Upstream(string url, string ua, string referer, long from, long to)
    {
        HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
        req.AddRange(from, to);
        req.UserAgent = ua != "" ? ua : "VLC/3.0.20 LibVLC/3.0.20";   // no User-Agent from yt-dlp: what VLC itself sends
        if (referer != "") req.Referer = referer;
        req.Timeout = 30000;
        req.ReadWriteTimeout = 30000;
        req.AllowAutoRedirect = true;
        return (HttpWebResponse)req.GetResponse();
    }

    static void Handle(string head, Stream s)
    {
        string[] lines = head.Split(new string[] { "\r\n" }, StringSplitOptions.None);
        string[] first = lines[0].Split(' ');
        if (first.Length < 3) return;
        bool body = first[0] != "HEAD";
        string target = first[1], path = target, query = "";
        int qm = target.IndexOf('?');
        if (qm >= 0) { path = target.Substring(0, qm); query = target.Substring(qm + 1); }
        if (path == "/" + secret + "/ping") { Reply(s, "200 OK", body); return; }
        if (path != "/" + secret + "/s") { Reply(s, "404 Not Found", body); return; }
        string url = Query(query, "u"), ua = Query(query, "ua"), referer = Query(query, "ref");
        if (!url.StartsWith("https://")) { Reply(s, "400 Bad Request", body); return; }

        Match range = null;
        foreach (string l in lines)
            if (l.StartsWith("Range:", StringComparison.OrdinalIgnoreCase))
                range = Regex.Match(l.Substring(6).Trim(), @"^bytes=(\d*)-(\d*)$");
        bool ranged = range != null && range.Success;
        long start = ranged && range.Groups[1].Value != "" ? long.Parse(range.Groups[1].Value) : 0;
        long lastWanted = ranged && range.Groups[2].Value != "" ? long.Parse(range.Groups[2].Value) : long.MaxValue;

        HttpWebResponse r;
        try { r = Upstream(url, ua, referer, start, Math.Min(start + Chunk - 1, lastWanted)); }
        catch (WebException e)
        {
            HttpWebResponse er = e.Response as HttpWebResponse;
            if (er != null && (int)er.StatusCode == 416) { Reply(s, "416 Range Not Satisfiable", body); return; }
            Log("upstream: " + (er != null ? "HTTP " + (int)er.StatusCode : e.Message));
            Reply(s, "502 Bad Gateway", body);
            return;
        }
        long total = -1;
        Match cr = Regex.Match(r.Headers["Content-Range"] ?? "", @"bytes \d+-\d+/(\d+)");
        if (cr.Success) total = long.Parse(cr.Groups[1].Value);
        else if (r.StatusCode == HttpStatusCode.OK && r.ContentLength >= 0) total = start + r.ContentLength;
        if (total < 0) { r.Close(); Log("upstream gave no length"); Reply(s, "502 Bad Gateway", body); return; }
        long end = Math.Min(lastWanted, total - 1);
        string headers = "Content-Type: " + (r.ContentType ?? "application/octet-stream") + "\r\n" +
            "Accept-Ranges: bytes\r\nContent-Length: " + (end - start + 1) + "\r\n";
        if (ranged) headers += "Content-Range: bytes " + start + "-" + end + "/" + total + "\r\n";
        WriteHead(s, ranged ? "206 Partial Content" : "200 OK", headers);
        if (!body) { r.Close(); return; }

        byte[] buf = new byte[64 * 1024];
        long pos = start;
        while (true)
        {
            using (Stream up = r.GetResponseStream())
            {
                int n;
                while (pos <= end && (n = up.Read(buf, 0, (int)Math.Min(buf.Length, end - pos + 1))) > 0)
                {
                    s.Write(buf, 0, n);
                    pos += n;
                    last = DateTime.UtcNow;
                }
            }
            r.Close();
            if (pos > end) return;
            r = null;
            for (int attempt = 0; attempt < 3 && r == null; attempt++)   // next chunk (retry a dropped one)
            {
                try { r = Upstream(url, ua, referer, pos, Math.Min(pos + Chunk - 1, end)); }
                catch (WebException e) { Log("chunk at " + pos + ": " + e.Message); Thread.Sleep(1000 * (attempt + 1)); }
            }
            if (r == null) return;
        }
    }
}
