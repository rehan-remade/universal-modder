// City Dashboard — READ-ONLY mod for Cities: Skylines 1.
// Serves a page at http://127.0.0.1:19680 with every number of the city, a detailed map and suggestions.
// It builds nothing, changes no budget and does not touch the simulation: it only reads data when the page asks.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using ColossalFramework;
using ColossalFramework.Globalization;
using ColossalFramework.IO;
using ColossalFramework.Plugins;
using ICities;
using UnityEngine;

namespace PainelCidade
{
    public class Mod : IUserMod
    {
        public Mod() { Painel.Boot(); }
        public string Name { get { return "City Dashboard"; } }
        public string Description { get { return "City statistics, a detailed map and suggestions at http://127.0.0.1:19680 (read-only)."; } }
        public void OnEnabled() { Painel.Start(); }
        public void OnDisabled() { Painel.Stop(); }
    }

    public class Pump : MonoBehaviour
    {
        void Update() { Painel.Tick(); }
    }

    /// Minimal JSON writer (automatic commas).
    public class JW
    {
        public StringBuilder sb = new StringBuilder(1 << 16);
        List<bool> need = new List<bool>();
        bool afterKey;
        void Pre()
        {
            if (afterKey) { afterKey = false; return; }
            if (need.Count > 0) { if (need[need.Count - 1]) sb.Append(','); else need[need.Count - 1] = true; }
        }
        void Str(string s)
        {
            sb.Append('"');
            foreach (char ch in s)
            {
                if (ch == '"') sb.Append("\\\"");
                else if (ch == '\\') sb.Append("\\\\");
                else if (ch == '\n') sb.Append("\\n");
                else if (ch < 32) sb.Append(' ');
                else sb.Append(ch);
            }
            sb.Append('"');
        }
        public JW K(string k) { Pre(); Str(k); sb.Append(':'); afterKey = true; return this; }
        public JW O() { Pre(); sb.Append('{'); need.Add(false); return this; }
        public JW A() { Pre(); sb.Append('['); need.Add(false); return this; }
        public JW EO() { sb.Append('}'); need.RemoveAt(need.Count - 1); return this; }
        public JW EA() { sb.Append(']'); need.RemoveAt(need.Count - 1); return this; }
        public JW Raw(string json) { Pre(); sb.Append(json); return this; }
        public JW V(long v) { Pre(); sb.Append(v); return this; }
        public JW V(double v) { Pre(); sb.Append((double.IsNaN(v) || double.IsInfinity(v)) ? "0" : v.ToString("0.##", CultureInfo.InvariantCulture)); return this; }
        public JW V(bool v) { Pre(); sb.Append(v ? "true" : "false"); return this; }
        public JW V(string s) { Pre(); if (s == null) sb.Append("null"); else Str(s); return this; }
        public JW P(string k, long v) { return K(k).V(v); }
        public JW P(string k, double v) { return K(k).V(v); }
        public JW P(string k, bool v) { return K(k).V(v); }
        public JW P(string k, string v) { return K(k).V(v); }
        public override string ToString() { return sb.ToString(); }
    }

    public static class Painel
    {
        public const int PORTA = 19680;
        static bool booted, running, primeiraVez;
        static TcpListener listener;
        static Thread thread;
        static readonly object qlock = new object();
        static Queue<Action> fila = new Queue<Action>();
        static string pastaMod, pastaDados;
        static float relogio;

        // weekly history (in memory + one CSV per city)
        static string cidadeHist = null;
        static List<string> hist = new List<string>();
        static long semanaAnterior = -1;
        static DateTime ultimaData = DateTime.MinValue;
        static DateTime dataRitmo; static float tRitmo; static double diasPorSegundo;

        static void Log(string s) { Debug.Log("[CityDashboard] " + s); }

        public static void Boot()
        {
            if (booted) return;
            booted = true;
            try
            {
                GameObject go = new GameObject("PainelCidadePump");
                go.AddComponent<Pump>();
                UnityEngine.Object.DontDestroyOnLoad(go);
                primeiraVez = true;
            }
            catch (Exception e) { Log("boot: " + e); }
        }

        public static void Start()
        {
            if (running) return;
            running = true;
            thread = new Thread(Escutar);
            thread.IsBackground = true;
            thread.Start();
            Log("server started on port " + PORTA);
        }

        public static void Stop()
        {
            running = false;
            try { if (listener != null) listener.Stop(); } catch { }
            listener = null;
            Log("server stopped");
        }

        static bool Carregado()
        {
            return Singleton<LoadingManager>.exists && Singleton<LoadingManager>.instance.m_loadingComplete && Singleton<SimulationManager>.exists;
        }

        public static void Tick()
        {
            // 1) the first time the game sees the mod it enables itself (after that it respects the Content Manager)
            if (primeiraVez)
            {
                primeiraVez = false;
                try
                {
                    // FindPluginInfo skips disabled mods, so look through the full list
                    PluginManager.PluginInfo pi = null;
                    foreach (PluginManager.PluginInfo p in Singleton<PluginManager>.instance.GetPluginsInfo())
                        if (p.ContainsAssembly(typeof(Mod).Assembly)) { pi = p; break; }
                    if (pi == null) pastaMod = Path.Combine(DataLocation.modsPath, "CityDashboard");
                    if (pi != null)
                    {
                        pastaMod = pi.modPath;
                        string marca = Path.Combine(pastaMod, "enabled-once.txt");
                        if (!File.Exists(marca))
                        {
                            File.WriteAllText(marca, "City Dashboard enabled itself on first run. To turn it off: Content Manager > Mods.\n");
                            if (!pi.isEnabled) pi.isEnabled = true;
                        }
                    }
                    pastaDados = Path.Combine(DataLocation.localApplicationData, "CityDashboard");
                    Directory.CreateDirectory(pastaDados);
                }
                catch (Exception e) { Log("first run: " + e); }
            }
            // 2) requests from the page
            while (true)
            {
                Action a = null;
                lock (qlock) { if (fila.Count > 0) a = fila.Dequeue(); }
                if (a == null) break;
                try { a(); } catch (Exception e) { Log("request: " + e); }
            }
            // 3) history: one line per in-game week
            relogio += Time.unscaledDeltaTime;
            if (relogio < 2f) return;
            relogio = 0f;
            try { if (running && Carregado()) Amostrar(); } catch (Exception e) { Log("sample: " + e.Message); }
            try
            {
                if (running && Carregado())
                {
                    SimulationManager sm = Singleton<SimulationManager>.instance;
                    if (!sm.SimulationPaused && !sm.ForcedSimulationPaused) sm.AddAction(DiaNoite.Amostra);
                }
            }
            catch (Exception e) { Log("day/night: " + e.Message); }
        }

        static string NomeArquivo(string cidade)
        {
            StringBuilder sb = new StringBuilder();
            foreach (char c in cidade ?? "cidade") sb.Append(char.IsLetterOrDigit(c) ? c : '_');
            return Path.Combine(pastaDados ?? ".", sb.ToString() + ".csv");
        }

        static void Amostrar()
        {
            SimulationManager sm = Singleton<SimulationManager>.instance;
            string cidade = sm.m_metaData.m_CityName ?? "cidade";
            string hoje = sm.m_currentGameTime.ToString("yyyy-MM-dd");
            if (cidade != cidadeHist || sm.m_currentGameTime < ultimaData.AddDays(-2))
            {
                // new city in this session, or an older save was loaded: re-read the CSV and drop what is "in the future"
                cidadeHist = cidade; semanaAnterior = -1;
                lock (hist)
                {
                    hist.Clear();
                    try
                    {
                        string arq = NomeArquivo(cidade);
                        if (File.Exists(arq))
                        {
                            string[] ls = File.ReadAllLines(arq);
                            bool cortou = false;
                            for (int i = Math.Max(0, ls.Length - 4000); i < ls.Length; i++)
                            {
                                if (ls[i].Length < 10) continue;
                                if (string.CompareOrdinal(ls[i].Substring(0, 10), hoje) >= 0) { cortou = true; continue; }
                                hist.Add(ls[i]);
                            }
                            if (cortou) File.WriteAllLines(arq, hist.ToArray());
                        }
                    }
                    catch { }
                }
                dataRitmo = sm.m_currentGameTime; tRitmo = Time.realtimeSinceStartup;
            }
            ultimaData = sm.m_currentGameTime;
            float agora = Time.realtimeSinceStartup;
            if (agora - tRitmo >= 20f)
            {
                diasPorSegundo = (sm.m_currentGameTime - dataRitmo).TotalDays / (agora - tRitmo);
                dataRitmo = sm.m_currentGameTime; tRitmo = agora;
            }
            long semana = sm.m_currentGameTime.Ticks / (TimeSpan.TicksPerDay * 7);
            if (semana == semanaAnterior) return;
            semanaAnterior = semana;
            District d = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
            EconomyManager em = Singleton<EconomyManager>.instance;
            ZoneManager zm = Singleton<ZoneManager>.instance;
            long inc, exp;
            em.GetIncomeAndExpenses(ItemClass.Service.None, ItemClass.SubService.None, ItemClass.Level.None, out inc, out exp);
            long empregos = d.m_commercialData.m_finalHomeOrWorkCount + d.m_industrialData.m_finalHomeOrWorkCount + d.m_officeData.m_finalHomeOrWorkCount + d.m_playerData.m_finalHomeOrWorkCount;
            string linha = string.Join(",", new string[] {
                hoje, d.m_populationData.m_finalCount.ToString(), (em.LastCashAmount / 100).ToString(),
                (inc / 100).ToString(), (exp / 100).ToString(), zm.m_residentialDemand.ToString(), zm.m_commercialDemand.ToString(), zm.m_workplaceDemand.ToString(),
                d.GetUnemployment().ToString(), d.m_finalHappiness.ToString(), empregos.ToString(), d.m_residentialData.m_finalHomeOrWorkCount.ToString(),
                d.GetLandValue().ToString(), d.m_finalCrimeRate.ToString() });
            lock (hist)
            {
                hist.Add(linha);
                if (hist.Count > 6000) hist.RemoveRange(0, 1000);
            }
            try { File.AppendAllText(NomeArquivo(cidade), linha + "\n"); } catch { }
        }

        // ---------- minimal HTTP server ----------
        static void Escutar()
        {
            while (running)
            {
                try
                {
                    for (int i = 0; i < 100 && pastaMod == null; i++) Thread.Sleep(100);   // the mod folder is discovered on the first frame
                    bool rede = pastaMod != null && File.Exists(Path.Combine(pastaMod, "open-to-lan.txt"));
                    listener = new TcpListener(rede ? IPAddress.Any : IPAddress.Loopback, PORTA);
                    Log(rede ? "open to the local network" : "this computer only (127.0.0.1)");
                    listener.Start();
                    while (running)
                    {
                        TcpClient c = listener.AcceptTcpClient();
                        Thread t = new Thread(() => Atender(c));
                        t.IsBackground = true;
                        t.Start();
                    }
                }
                catch (Exception e)
                {
                    if (running) { Log("listen: " + e.Message); Thread.Sleep(3000); }
                }
            }
        }

        static void Atender(TcpClient c)
        {
            try
            {
                using (c)
                {
                    c.ReceiveTimeout = 5000;
                    NetworkStream ns = c.GetStream();
                    StreamReader r = new StreamReader(ns, Encoding.UTF8);
                    string req = r.ReadLine();
                    if (req == null) return;
                    string l;
                    while ((l = r.ReadLine()) != null && l.Length > 0) { }
                    string[] p = req.Split(' ');
                    string caminho = p.Length > 1 ? p[1] : "/";
                    int q = caminho.IndexOf('?');
                    if (q >= 0) caminho = caminho.Substring(0, q);
                    string tipo = "application/json; charset=utf-8";
                    int codigo = 200;
                    long custo = -1;   // milliseconds spent inside the game to build the response
                    byte[] corpo;
                    if (caminho == "/" || caminho == "/index.html")
                    {
                        tipo = "text/html; charset=utf-8";
                        string arq = Path.Combine(Path.Combine(pastaMod ?? ".", "web"), "index.html");
                        corpo = File.Exists(arq) ? File.ReadAllBytes(arq) : Encoding.UTF8.GetBytes("<h1>City Dashboard</h1><p>File web/index.html not found at " + arq + "</p>");
                    }
                    else if (caminho == "/api/cidade") { corpo = Encoding.UTF8.GetBytes(NaPrincipal(Coleta.Cidade, 1f, "cidade")); custo = TempoDe("cidade"); }
                    else if (caminho == "/api/mapa") { corpo = Encoding.UTF8.GetBytes(NaPrincipal(Coleta.Mapa, 1.5f, "mapa")); custo = TempoDe("mapa"); }
                    else if (caminho == "/api/servicos") { corpo = Encoding.UTF8.GetBytes(NaPrincipal(Coleta.Servicos, 3f, "servicos")); custo = TempoDe("servicos"); }
                    else if (caminho == "/api/historico") corpo = Encoding.UTF8.GetBytes(Historico());
                    else if (caminho == "/api/dianoite") corpo = Encoding.UTF8.GetBytes(Carregado() ? DiaNoite.Json() : "{\"carregado\":false}");
                    else { codigo = 404; corpo = Encoding.UTF8.GetBytes("{\"erro\":\"not found\"}"); }
                    string cab = "HTTP/1.1 " + codigo + (codigo == 200 ? " OK" : " Not Found") + "\r\nContent-Type: " + tipo + "\r\nContent-Length: " + corpo.Length +
                                 (custo >= 0 ? "\r\nX-Coleta-Ms: " + custo : "") + "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
                    byte[] cb = Encoding.ASCII.GetBytes(cab);
                    ns.Write(cb, 0, cb.Length);
                    ns.Write(corpo, 0, corpo.Length);
                    ns.Flush();
                }
            }
            catch { }
        }

        static string Historico()
        {
            JW j = new JW();
            j.O().P("cidade", cidadeHist).K("colunas").A();
            foreach (string c in new string[] { "data", "pop", "caixa", "receita", "despesa", "demR", "demC", "demW", "desemprego", "felicidade", "empregos", "moradias", "valorTerreno", "crime" }) j.V(c);
            j.EA().K("linhas").A();
            string[] copia;
            lock (hist) copia = hist.ToArray();
            int passo = Math.Max(1, copia.Length / 600);
            for (int i = 0; i < copia.Length; i += passo) j.V(copia[i]);
            if (copia.Length > 0 && (copia.Length - 1) % passo != 0) j.V(copia[copia.Length - 1]);
            return j.EA().EO().ToString();
        }

        // per-route cache: the collection runs inside the game only when the page asks
        static Dictionary<string, string> cache = new Dictionary<string, string>();
        static Dictionary<string, DateTime> cacheQuando = new Dictionary<string, DateTime>();

        static readonly object coletaLock = new object();
        static Dictionary<string, long> tempos = new Dictionary<string, long>();
        public static long TempoDe(string chave) { lock (cache) { long t; return tempos.TryGetValue(chave, out t) ? t : -1; } }

        /// Runs the collection inside the game and returns the JSON. It happens on the simulation thread: a large map
        /// costs a few milliseconds of simulation but holds no frame on screen. If the simulation does not
        /// answer within 3 s, the same request is handed to the main thread.
        static string NaPrincipal(Func<string> f, float validade, string chave)
        {
            lock (coletaLock)
            {
                lock (cache)
                {
                    DateTime t;
                    if (cacheQuando.TryGetValue(chave, out t) && (DateTime.UtcNow - t).TotalSeconds < validade) return cache[chave];
                }
                if (!Carregado()) return "{\"carregado\":false}";
                string res = null;
                int feito = 0;
                long ms = 0;
                ManualResetEvent ok = new ManualResetEvent(false);
                Action a = () =>
                {
                    if (Interlocked.Exchange(ref feito, 1) != 0) return;   // only one of the two threads runs it
                    System.Diagnostics.Stopwatch sw = System.Diagnostics.Stopwatch.StartNew();
                    try { res = Carregado() ? f() : "{\"carregado\":false}"; }
                    catch (Exception e) { res = "{\"carregado\":true,\"erro\":" + new JW().V(e.GetType().Name + ": " + e.Message + " | " + (e.StackTrace ?? "").Split('\n')[0]).ToString() + "}"; Log(chave + ": " + e); }
                    finally { ms = sw.ElapsedMilliseconds; ok.Set(); }
                };
                bool naSim = false;
                try { Singleton<SimulationManager>.instance.AddAction(a); naSim = true; } catch (Exception e) { Log("AddAction: " + e.Message); }
                if (!naSim || !ok.WaitOne(3000))
                {
                    lock (qlock) fila.Enqueue(a);
                    if (!ok.WaitOne(20000)) return "{\"carregado\":false,\"erro\":\"the game did not answer\"}";
                }
                lock (cache) { cache[chave] = res; cacheQuando[chave] = DateTime.UtcNow; tempos[chave] = ms; }
                return res;
            }
        }

        public static double DiasPorSegundo { get { return diasPorSegundo; } }
    }

    /// Usage of each service split into day and night. Keeps a moving average (~5 min of running game per period)
    /// and the recent peak, so the page can compare the two periods and suggest a budget for each.
    public static class DiaNoite
    {
        public static readonly string[] CH = { "energia", "agua", "esgoto", "lixo", "saude", "celas", "ensino",
            "vLixo", "vSaude", "vFuneraria", "vBombeiro", "vPolicia", "vRuas", "trafego", "movimento" };
        // vehicles per building type: the AI field that says how many the building owns (the index adds to "vLixo")
        static readonly string[] CAMPOS_V = { "m_garbageTruckCount", "m_ambulanceCount", "m_hearseCount", "m_fireTruckCount", "m_policeCarCount", "m_maintenanceTruckCount" };
        const int N = 15, V0 = 7;
        const double PESO = 0.993, PICO = 0.998;
        static double[,] sd = new double[2, N], sc = new double[2, N], pico = new double[2, N];
        static double[] peso = new double[2];
        static long[] n = new long[2];
        static string cidade; static bool noite, ciclo; static float hora;
        static readonly object trava = new object();
        static Dictionary<Type, KeyValuePair<FieldInfo, int>> campos = new Dictionary<Type, KeyValuePair<FieldInfo, int>>();

        /// Runs on the simulation thread.
        public static void Amostra()
        {
            try
            {
                if (!Singleton<LoadingManager>.exists || !Singleton<LoadingManager>.instance.m_loadingComplete) return;
                SimulationManager sm = Singleton<SimulationManager>.instance;
                District di = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
                double[] d = new double[N], c = new double[N];
                d[0] = di.GetElectricityConsumption(); c[0] = di.GetElectricityCapacity();
                d[1] = di.GetWaterConsumption(); c[1] = di.GetWaterCapacity();
                d[2] = di.GetSewageAccumulation(); c[2] = di.GetSewageCapacity();
                d[3] = di.GetGarbageAccumulation(); c[3] = di.GetIncinerationCapacity();
                d[4] = di.GetSickCount(); c[4] = di.GetHealCapacity();
                d[5] = di.GetCriminalAmount(); c[5] = di.GetCriminalCapacity();
                d[6] = di.GetEducation1Need() + di.GetEducation2Need() + di.GetEducation3Need();
                c[6] = di.GetEducation1Capacity() + di.GetEducation2Capacity() + di.GetEducation3Capacity();
                BuildingManager bm = Singleton<BuildingManager>.instance;
                VehicleManager vm = Singleton<VehicleManager>.instance;
                for (int i = 1; i < bm.m_buildings.m_size; i++)
                {
                    if ((bm.m_buildings.m_buffer[i].m_flags & Building.Flags.Created) == 0) continue;
                    BuildingInfo info = bm.m_buildings.m_buffer[i].Info;
                    if (info == null || !(info.m_buildingAI is PlayerBuildingAI)) continue;
                    Type t = info.m_buildingAI.GetType();
                    KeyValuePair<FieldInfo, int> kv;
                    if (!campos.TryGetValue(t, out kv))
                    {
                        kv = new KeyValuePair<FieldInfo, int>(null, -1);
                        for (int k = 0; k < CAMPOS_V.Length; k++)
                        {
                            FieldInfo f = t.GetField(CAMPOS_V[k]);
                            if (f != null && f.FieldType == typeof(int)) { kv = new KeyValuePair<FieldInfo, int>(f, k); break; }
                        }
                        campos[t] = kv;
                    }
                    if (kv.Key == null) continue;
                    int tem = (int)kv.Key.GetValue(info.m_buildingAI);
                    if (tem <= 0) continue;
                    int disponiveis = (bm.m_buildings.m_buffer[i].m_productionRate * tem + 99) / 100;
                    int usados = 0, guarda = 0;
                    ushort v = bm.m_buildings.m_buffer[i].m_ownVehicles;
                    while (v != 0 && guarda++ < 16384) { usados++; v = vm.m_vehicles.m_buffer[v].m_nextOwnVehicle; }
                    d[V0 + kv.Value] += usados; c[V0 + kv.Value] += disponiveis;
                }
                NetManager nm = Singleton<NetManager>.instance;
                long soma = 0; int trechos = 0;
                for (int i = 1; i < nm.m_segments.m_size; i++)
                {
                    if ((nm.m_segments.m_buffer[i].m_flags & NetSegment.Flags.Created) == 0) continue;
                    NetInfo ni = nm.m_segments.m_buffer[i].Info;
                    if (ni == null || ni.m_class.m_service != ItemClass.Service.Road) continue;
                    soma += nm.m_segments.m_buffer[i].m_trafficDensity; trechos++;
                }
                d[13] = trechos > 0 ? (double)soma / trechos : 0; c[13] = 100;
                d[14] = Singleton<CitizenManager>.instance.m_instanceCount; c[14] = 0;
                string nome = sm.m_metaData.m_CityName ?? "";
                lock (trava)
                {
                    if (nome != cidade)
                    {
                        cidade = nome;
                        Array.Clear(sd, 0, sd.Length); Array.Clear(sc, 0, sc.Length); Array.Clear(pico, 0, pico.Length);
                        peso[0] = peso[1] = 0; n[0] = n[1] = 0;
                    }
                    ciclo = sm.m_enableDayNight; noite = ciclo && sm.m_isNightTime; hora = sm.m_currentDayTimeHour;
                    int p = noite ? 1 : 0;
                    peso[p] = peso[p] * PESO + 1; n[p]++;
                    for (int k = 0; k < N; k++)
                    {
                        sd[p, k] = sd[p, k] * PESO + d[k]; sc[p, k] = sc[p, k] * PESO + c[k];
                        pico[p, k] = Math.Max(pico[p, k] * PICO, c[k] > 0 ? d[k] / c[k] : 0);
                    }
                }
            }
            catch (Exception e) { Debug.Log("[CityDashboard] day/night: " + e.Message); }
        }

        /// Answers straight from memory: does not touch the game.
        public static string Json()
        {
            JW j = new JW();
            lock (trava)
            {
                j.O().P("carregado", true).P("cidade", cidade).P("ciclo", ciclo).P("noite", noite).P("hora", (double)hora)
                 .K("amostras").A().V(n[0]).V(n[1]).EA().P("segundosPorAmostra", 2).K("itens").O();
                for (int k = 0; k < N; k++)
                {
                    j.K(CH[k]).A();
                    for (int p = 0; p < 2; p++)
                        j.A().V(peso[p] > 0 ? sd[p, k] / peso[p] : 0).V(peso[p] > 0 ? sc[p, k] / peso[p] : 0).V(pico[p, k] * 100).EA();
                    j.EA();
                }
                j.EO().EO();
            }
            return j.ToString();
        }
    }

    public static class Coleta
    {
        static NetManager NM { get { return Singleton<NetManager>.instance; } }
        static BuildingManager BM { get { return Singleton<BuildingManager>.instance; } }
        static ZoneManager ZM { get { return Singleton<ZoneManager>.instance; } }
        static SimulationManager SM { get { return Singleton<SimulationManager>.instance; } }

        static void Priv(JW j, string k, DistrictPrivateData d)
        {
            j.K(k).O().P("total", d.m_finalHomeOrWorkCount).P("ocupados", d.m_finalAliveCount).P("vazios", d.m_finalEmptyCount).P("predios", d.m_finalBuildingCount)
             .P("abandonados", d.m_finalAbandonedCount).P("queimados", d.m_finalBurnedCount).P("desabados", d.m_finalCollapsedCount)
             .P("saude", d.m_finalHealth).P("felicidade", d.m_finalHappiness).P("crime", d.m_finalCrimeRate).P("nivelMedio", d.m_finalLevel).P("area", d.m_finalBuildingArea)
             .K("niveis").A().V(d.m_finalLevel1).V(d.m_finalLevel2).V(d.m_finalLevel3).V(d.m_finalLevel4).V(d.m_finalLevel5).EA().EO();
        }

        static void Edu(JW j, string k, DistrictEducationData e)
        {
            j.K(k).O().P("pessoas", e.m_finalCount).P("aptos", e.m_finalEligibleWorkers).P("desempregados", e.m_finalUnemployed).P("semTeto", e.m_finalHomeless).EO();
        }

        static void Rec(JW j, string k, DistrictResourceData r)
        {
            j.K(k).O().P("minerio", r.m_finalOre).P("petroleo", r.m_finalOil).P("madeira", r.m_finalForestry).P("agricola", r.m_finalAgricultural).P("mercadorias", r.m_finalGoods).P("correio", r.m_finalMail).P("peixe", r.m_finalFish).EO();
        }

        static bool EhEstrada(NetInfo i) { return i != null && i.m_class.m_service == ItemClass.Service.Road; }

        /// Connected components of the road network (union of nodes): returns the "parent" of each road node.
        static Dictionary<ushort, ushort> Componentes()
        {
            Dictionary<ushort, ushort> pai = new Dictionary<ushort, ushort>();
            Func<ushort, ushort> achar = null;
            achar = (x) => { ushort p; if (!pai.TryGetValue(x, out p)) { pai[x] = x; return x; } while (p != x) { ushort g = pai[p]; pai[x] = g; x = p; p = g; } return x; };
            for (int i = 1; i < NM.m_segments.m_size; i++)
            {
                NetSegment s = NM.m_segments.m_buffer[i];
                if ((s.m_flags & NetSegment.Flags.Created) == 0 || !EhEstrada(s.Info)) continue;
                ushort a = achar(s.m_startNode), b = achar(s.m_endNode);
                if (a != b) pai[a] = b;
            }
            Dictionary<ushort, ushort> raiz = new Dictionary<ushort, ushort>();
            List<ushort> chaves = new List<ushort>(pai.Keys);
            foreach (ushort k in chaves) raiz[k] = achar(k);
            return raiz;
        }

        public static string Cidade()
        {
            DistrictManager dm = Singleton<DistrictManager>.instance;
            District d = dm.m_districts.m_buffer[0];
            EconomyManager em = Singleton<EconomyManager>.instance;
            JW j = new JW();
            j.O().P("carregado", true);
            // --- general
            j.K("geral").O().P("cidade", SM.m_metaData.m_CityName).P("data", SM.m_currentGameTime.ToString("yyyy-MM-dd")).P("pausado", SM.SimulationPaused || SM.ForcedSimulationPaused)
             .P("velocidade", SM.SelectedSimulationSpeed).P("diasPorSegundo", Painel.DiasPorSegundo).P("lotes", Singleton<GameAreaManager>.instance.m_areaCount)
             .P("lotesMax", Singleton<GameAreaManager>.instance.MaxAreaCount).EO();
            // --- money
            long inc, exp;
            em.GetIncomeAndExpenses(ItemClass.Service.None, ItemClass.SubService.None, ItemClass.Level.None, out inc, out exp);
            j.K("dinheiro").O().P("caixa", em.LastCashAmount / 100).P("receita", inc / 100).P("despesa", exp / 100).K("porServico").O();
            foreach (ItemClass.Service s in Enum.GetValues(typeof(ItemClass.Service)))
            {
                if (s == ItemClass.Service.None) continue;
                long a, b;
                em.GetIncomeAndExpenses(s, ItemClass.SubService.None, ItemClass.Level.None, out a, out b);
                if (a == 0 && b == 0) continue;
                j.K(s.ToString()).A().V(a / 100).V(b / 100).EA();
            }
            j.EO().K("impostos").O()
             .P("ResidencialBaixa", em.GetTaxRate(ItemClass.Service.Residential, ItemClass.SubService.ResidentialLow, ItemClass.Level.Level1))
             .P("ResidencialAlta", em.GetTaxRate(ItemClass.Service.Residential, ItemClass.SubService.ResidentialHigh, ItemClass.Level.Level1))
             .P("ComercialBaixa", em.GetTaxRate(ItemClass.Service.Commercial, ItemClass.SubService.CommercialLow, ItemClass.Level.Level1))
             .P("ComercialAlta", em.GetTaxRate(ItemClass.Service.Commercial, ItemClass.SubService.CommercialHigh, ItemClass.Level.Level1))
             .P("Industria", em.GetTaxRate(ItemClass.Service.Industrial, ItemClass.SubService.IndustrialGeneric, ItemClass.Level.Level1))
             .P("Escritorios", em.GetTaxRate(ItemClass.Service.Office, ItemClass.SubService.None, ItemClass.Level.Level1)).EO();
            j.K("orcamento").O();
            foreach (ItemClass.Service s in new ItemClass.Service[] { ItemClass.Service.Electricity, ItemClass.Service.Water, ItemClass.Service.Garbage, ItemClass.Service.HealthCare, ItemClass.Service.FireDepartment,
                     ItemClass.Service.PoliceDepartment, ItemClass.Service.Education, ItemClass.Service.Road, ItemClass.Service.Beautification, ItemClass.Service.Monument })
                j.K(s.ToString()).A().V(em.GetBudget(s, ItemClass.SubService.None, false)).V(em.GetBudget(s, ItemClass.SubService.None, true)).EA();
            j.EO().K("politicas").A();
            foreach (DistrictPolicies.Policies pol in Enum.GetValues(typeof(DistrictPolicies.Policies)))
            {
                if (pol == DistrictPolicies.Policies.None) continue;
                try { if (dm.IsCityPolicySet(pol)) j.V(NomePolitica(pol.ToString())); } catch { }
            }
            j.EA().EO();
            // --- demand (with the inputs of the game's formula)
            long empregos = d.m_commercialData.m_finalHomeOrWorkCount + d.m_industrialData.m_finalHomeOrWorkCount + d.m_officeData.m_finalHomeOrWorkCount + d.m_playerData.m_finalHomeOrWorkCount;
            long vagasLivres = d.m_commercialData.m_finalEmptyCount + d.m_industrialData.m_finalEmptyCount + d.m_officeData.m_finalEmptyCount + d.m_playerData.m_finalEmptyCount;
            long desempregados = d.m_educated0Data.m_finalUnemployed + d.m_educated1Data.m_finalUnemployed + d.m_educated2Data.m_finalUnemployed + d.m_educated3Data.m_finalUnemployed;
            j.K("demanda").O().P("r", ZM.m_residentialDemand).P("c", ZM.m_commercialDemand).P("w", ZM.m_workplaceDemand)
             .P("rAtual", ZM.m_actualResidentialDemand).P("cAtual", ZM.m_actualCommercialDemand).P("wAtual", ZM.m_actualWorkplaceDemand)
             .P("ajusteImpostoR", d.CalculateResidentialDemandOffset()).P("ajusteImpostoC", d.CalculateCommercialDemandOffset()).P("ajusteImpostoW", d.CalculateWorkplaceDemandOffset())
             .P("empregos", empregos).P("vagasLivres", vagasLivres).P("desempregados", desempregados).EO();
            // --- population
            j.K("populacao").O().P("total", d.m_populationData.m_finalCount)
             .K("idades").A().V(d.m_childData.m_finalCount).V(d.m_teenData.m_finalCount).V(d.m_youngData.m_finalCount).V(d.m_adultData.m_finalCount).V(d.m_seniorData.m_finalCount).EA()
             .P("nascimentos", d.m_birthData.m_finalCount).P("mortes", d.m_deathData.m_finalCount).P("expectativa", d.GetAverageLifespan())
             .P("felicidade", d.m_finalHappiness).P("desempregoPct", d.GetUnemployment()).P("trabalhadores", d.GetWorkerCount()).P("postos", d.GetWorkplaceCount());
            Edu(j, "semEstudo", d.m_educated0Data); Edu(j, "fundamental", d.m_educated1Data); Edu(j, "medio", d.m_educated2Data); Edu(j, "superior", d.m_educated3Data);
            j.K("turistas").A().V(d.m_tourist1Data.m_finalCount).V(d.m_tourist2Data.m_finalCount).V(d.m_tourist3Data.m_finalCount).EA()
             .K("visitasTuristas").A().V(d.m_tourist1Data.m_finalVisits).V(d.m_tourist2Data.m_finalVisits).V(d.m_tourist3Data.m_finalVisits).EA().EO();
            // --- sectors
            j.K("setores").O();
            Priv(j, "residencial", d.m_residentialData); Priv(j, "comercial", d.m_commercialData); Priv(j, "industrial", d.m_industrialData);
            Priv(j, "escritorios", d.m_officeData); Priv(j, "publico", d.m_playerData); Priv(j, "visitantes", d.m_visitorData);
            j.EO();
            // --- zones (8 m cells)
            long[] zt = new long[16], zv = new long[16];
            for (int i = 1; i < ZM.m_blocks.m_size; i++)
            {
                if ((ZM.m_blocks.m_buffer[i].m_flags & 1u) == 0) continue;
                ZoneBlock b = ZM.m_blocks.m_buffer[i];
                int rows = b.RowCount;
                ulong ocup = b.m_occupied1 | b.m_occupied2;
                for (int z = 0; z < rows; z++)
                    for (int x = 0; x < 4; x++)
                    {
                        ulong bit = 1UL << ((z << 3) | x);
                        if ((b.m_valid & bit) == 0 || (b.m_shared & bit) != 0) continue;
                        int t = (int)b.GetZone(x, z) & 15;
                        zt[t]++;
                        if ((ocup & bit) == 0) zv[t]++;
                    }
            }
            j.K("zonas").O();
            for (int k = 0; k < 16; k++) if (zt[k] > 0) j.K(((ItemClass.Zone)k).ToString()).A().V(zt[k]).V(zv[k]).EA();
            j.EO();
            // --- infrastructure
            j.K("infra").O()
             .K("energia").A().V(d.GetElectricityConsumption()).V(d.GetElectricityCapacity()).EA()
             .K("aquecimento").A().V(d.GetHeatingConsumption()).V(d.GetHeatingCapacity()).EA()
             .K("agua").A().V(d.GetWaterConsumption()).V(d.GetWaterCapacity()).EA()
             .K("esgoto").A().V(d.GetSewageAccumulation()).V(d.GetSewageCapacity()).EA()
             .K("reservaAgua").A().V(d.GetWaterStorageAmount()).V(d.GetWaterStorageCapacity()).EA()
             .P("poluicaoAgua", d.GetWaterPollution())
             .K("lixo").O().P("acumulado", d.GetGarbageAmount()).P("capacidadeAterros", d.GetGarbageCapacity()).P("producaoSemanal", d.GetGarbageAccumulation())
               .P("incineracaoSemanal", d.GetIncinerationCapacity()).P("pilhas", d.GetGarbagePiles()).EO().EO();
            // --- services
            j.K("servicos").O()
             .K("saude").O().P("capacidadeTratamento", d.GetHealCapacity()).P("doentes", d.GetSickCount()).P("hospitais", d.GetHospitalCount()).P("saudeMedia", d.m_residentialData.m_finalHealth).EO()
             .K("funeraria").O().P("corposAguardando", d.GetDeadCount()).P("sepultados", d.GetDeadAmount()).P("capacidadeCemiterios", d.GetDeadCapacity()).P("cremacaoSemanal", d.GetCremateCapacity()).P("cemiterios", d.GetCemetery()).EO()
             .K("educacao").O().K("fundamental").A().V(d.GetEducation1Need()).V(d.GetEducation1Capacity()).V(d.GetEducation1Rate()).EA()
               .K("medio").A().V(d.GetEducation2Need()).V(d.GetEducation2Capacity()).V(d.GetEducation2Rate()).EA()
               .K("superior").A().V(d.GetEducation3Need()).V(d.GetEducation3Capacity()).V(d.GetEducation3Rate()).EA()
               .K("bibliotecas").A().V(d.GetLibraryVisitorCount()).V(d.GetLibraryCapacity()).EA().EO()
             .K("policia").O().P("presos", d.GetCriminalAmount()).P("celas", d.GetCriminalCapacity()).P("taxaCrime", d.m_finalCrimeRate).EO().EO();
            // --- environment
            uint ore, oil, forest, fert, water, uOre, uOil, uForest, uFert;
            Singleton<NaturalResourceManager>.instance.CalculateUnlockedResources(out ore, out oil, out forest, out fert, out water);
            Singleton<NaturalResourceManager>.instance.CalculateUsedResources(out uOre, out uOil, out uForest, out uFert);
            j.K("ambiente").O().P("poluicaoSolo", d.GetGroundPollution()).P("valorTerreno", d.GetLandValue())
             .K("recursos").O().K("minerio").A().V(uOre).V(ore).EA().K("petroleo").A().V(uOil).V(oil).EA().K("floresta").A().V(uForest).V(forest).EA().K("soloFertil").A().V(uFert).V(fert).EA().P("agua", water).EO().EO();
            // --- foreign trade and industry
            j.K("comercioExterior").O().P("importTotal", d.GetImportAmount()).P("exportTotal", d.GetExportAmount());
            Rec(j, "importa", d.m_importData); Rec(j, "exporta", d.m_exportData);
            j.EO();
            j.K("industria").O()
             .K("generica").A().V(d.GetGenericIndustryArea()).V(d.GetGenericIndustryProductivity()).EA()
             .K("agricola").A().V(d.GetFarmingIndustryArea()).V(d.GetFarmingIndustryProductivity()).EA()
             .K("florestal").A().V(d.GetForestryIndustryArea()).V(d.GetForestryIndustryProductivity()).EA()
             .K("minerio").A().V(d.GetOreIndustryArea()).V(d.GetOreIndustryProductivity()).EA()
             .K("petroleo").A().V(d.GetOilIndustryArea()).V(d.GetOilIndustryProductivity()).EA().EO();
            // --- buildings: count per service and problems
            Dictionary<string, int> porServico = new Dictionary<string, int>();
            Dictionary<string, int[]> problemas = new Dictionary<string, int[]>();   // [total, major, fatal]
            int abandonados = 0, queimados = 0, desabados = 0, total = 0;
            for (int i = 1; i < BM.m_buildings.m_size; i++)
            {
                Building.Flags f = BM.m_buildings.m_buffer[i].m_flags;
                if ((f & Building.Flags.Created) == 0) continue;
                BuildingInfo info = BM.m_buildings.m_buffer[i].Info;
                if (info == null) continue;
                total++;
                string sv = info.m_class.m_service.ToString();
                int c; porServico.TryGetValue(sv, out c); porServico[sv] = c + 1;
                if ((f & Building.Flags.Abandoned) != 0) abandonados++;
                if ((f & Building.Flags.BurnedDown) != 0) queimados++;
                if ((f & Building.Flags.Collapsed) != 0) desabados++;
                if (BM.m_buildings.m_buffer[i].m_problems.IsNone) continue;
                string ps = BM.m_buildings.m_buffer[i].m_problems.ToString();
                bool grave = ps.IndexOf("MajorProblem") >= 0, fatal = ps.IndexOf("FatalProblem") >= 0;
                foreach (string parte in ps.Split(','))
                {
                    string nome = parte.Trim();
                    if (nome.Length == 0 || nome == "MajorProblem" || nome == "FatalProblem") continue;
                    int[] v;
                    if (!problemas.TryGetValue(nome, out v)) { v = new int[3]; problemas[nome] = v; }
                    v[0]++; if (grave) v[1]++; if (fatal) v[2]++;
                }
            }
            j.K("predios").O().P("total", total).P("abandonados", abandonados).P("queimados", queimados).P("desabados", desabados).K("porServico").O();
            foreach (KeyValuePair<string, int> kv in porServico) j.P(kv.Key, kv.Value);
            j.EO().K("problemas").O();
            foreach (KeyValuePair<string, int[]> kv in problemas) j.K(kv.Key).A().V(kv.Value[0]).V(kv.Value[1]).V(kv.Value[2]).EA();
            j.EO().EO();
            // --- traffic
            long soma = 0; int n = 0, acima50 = 0, acima90 = 0;
            List<KeyValuePair<int, int>> piores = new List<KeyValuePair<int, int>>();
            Dictionary<string, long[]> porTipo = new Dictionary<string, long[]>();
            for (int i = 1; i < NM.m_segments.m_size; i++)
            {
                NetSegment s = NM.m_segments.m_buffer[i];
                if ((s.m_flags & NetSegment.Flags.Created) == 0 || !EhEstrada(s.Info)) continue;
                int dens = s.m_trafficDensity;
                soma += dens; n++;
                if (dens >= 50) acima50++;
                if (dens >= 90) acima90++;
                if (dens >= 60) piores.Add(new KeyValuePair<int, int>(dens, i));
                long[] v;
                if (!porTipo.TryGetValue(s.Info.name, out v)) { v = new long[2]; porTipo[s.Info.name] = v; }
                v[0]++; v[1] += dens;
            }
            piores.Sort((a, b) => b.Key.CompareTo(a.Key));
            VehicleManager vm = Singleton<VehicleManager>.instance;
            j.K("transito").O().P("media", n > 0 ? soma / n : 0).P("trechos", n).P("acima50", acima50).P("acima90", acima90).P("veiculos", vm.m_vehicleCount).P("estacionados", vm.m_parkedCount)
             .K("porTipo").O();
            foreach (KeyValuePair<string, long[]> kv in porTipo) j.K(kv.Key).A().V(kv.Value[0]).V(kv.Value[0] > 0 ? kv.Value[1] / kv.Value[0] : 0).EA();
            j.EO().K("piores").A();
            for (int k = 0; k < piores.Count && k < 40; k++)
            {
                int id = piores[k].Value;
                NetSegment s = NM.m_segments.m_buffer[id];
                string nome = null;
                try { nome = NM.GetSegmentName((ushort)id); } catch { }
                j.A().V(id).V(piores[k].Key).V(nome ?? "").V(s.Info.name).V(Mathf.RoundToInt(s.m_middlePosition.x)).V(Mathf.RoundToInt(s.m_middlePosition.z)).EA();
            }
            j.EA().EO();
            // --- public transport
            TransportManager tm = Singleton<TransportManager>.instance;
            j.K("transporte").O().K("passageiros").O();
            foreach (TransportInfo.TransportType tt in Enum.GetValues(typeof(TransportInfo.TransportType)))
            {
                int ix = (int)tt;
                if (tm.m_passengers == null || ix < 0 || ix >= tm.m_passengers.Length) continue;
                uint a = tm.m_passengers[ix].m_residentPassengers.m_averageCount, b = tm.m_passengers[ix].m_touristPassengers.m_averageCount;
                if (a + b > 0) j.K(tt.ToString()).A().V(a).V(b).EA();
            }
            j.EO().K("linhas").A();
            for (int i = 1; i < tm.m_lines.m_size; i++)
            {
                TransportLine tl = tm.m_lines.m_buffer[i];
                if ((tl.m_flags & TransportLine.Flags.Created) == 0 || (tl.m_flags & (TransportLine.Flags.Temporary | TransportLine.Flags.Hidden)) != 0) continue;
                if (tl.Info == null) continue;
                string nome = null;
                try { nome = tm.GetLineName((ushort)i); } catch { }
                int paradas = 0; bool completa = false;
                try { paradas = tl.CountStops((ushort)i); completa = tl.Complete; } catch { }
                j.A().V(i).V(tl.Info.m_transportType.ToString()).V(nome ?? ("Line " + i)).V(paradas)
                 .V(tl.m_passengers.m_residentPassengers.m_averageCount).V(tl.m_passengers.m_touristPassengers.m_averageCount).V(completa).EA();
            }
            j.EA().EO();
            // --- outside connections (and whether the city's road network reaches each one)
            Dictionary<ushort, ushort> comp = Componentes();
            Dictionary<ushort, int> tam = new Dictionary<ushort, int>();
            for (int i = 1; i < NM.m_segments.m_size; i++)
            {
                NetSegment s = NM.m_segments.m_buffer[i];
                if ((s.m_flags & NetSegment.Flags.Created) == 0 || !EhEstrada(s.Info) || (s.m_flags & NetSegment.Flags.Untouchable) != 0) continue;
                if (s.Info.name.IndexOf("Highway") >= 0) continue;
                ushort r; if (comp.TryGetValue(s.m_startNode, out r)) { int c; tam.TryGetValue(r, out c); tam[r] = c + 1; }
            }
            ushort principal = 0; int maior = 0;
            foreach (KeyValuePair<ushort, int> kv in tam) if (kv.Value > maior) { maior = kv.Value; principal = kv.Key; }
            j.K("conexoes").A();
            FastList<ushort> oc = BM.GetOutsideConnections();
            for (int k = 0; k < oc.m_size; k++)
            {
                ushort id = oc.m_buffer[k];
                Building b = BM.m_buildings.m_buffer[id];
                if (b.Info == null) continue;
                string tipo = b.Info.m_class.m_service == ItemClass.Service.Road ? "Rodovia" : b.Info.m_class.m_subService.ToString().Replace("PublicTransport", "");
                int ligada = -1;   // -1 = not applicable
                if (b.Info.m_class.m_service == ItemClass.Service.Road && maior > 0)
                {
                    ligada = 0;
                    float melhor = 300f * 300f; ushort noPerto = 0;
                    for (int i = 1; i < NM.m_nodes.m_size; i++)
                    {
                        if ((NM.m_nodes.m_buffer[i].m_flags & NetNode.Flags.Created) == 0 || !EhEstrada(NM.m_nodes.m_buffer[i].Info)) continue;
                        Vector3 p = NM.m_nodes.m_buffer[i].m_position;
                        float dx = p.x - b.m_position.x, dz = p.z - b.m_position.z, d2 = dx * dx + dz * dz;
                        if (d2 < melhor) { melhor = d2; noPerto = (ushort)i; }
                    }
                    ushort r;
                    if (noPerto != 0 && comp.TryGetValue(noPerto, out r) && r == principal) ligada = 1;
                }
                j.A().V(tipo).V(Mathf.RoundToInt(b.m_position.x)).V(Mathf.RoundToInt(b.m_position.z)).V((b.m_flags & Building.Flags.Incoming) != 0).V((b.m_flags & Building.Flags.Outgoing) != 0).V(ligada).EA();
            }
            j.EA();
            // --- districts
            j.K("distritos").A();
            for (int i = 1; i < dm.m_districts.m_size; i++)
            {
                District di = dm.m_districts.m_buffer[i];
                if ((di.m_flags & District.Flags.Created) == 0) continue;
                string nome = null;
                try { nome = dm.GetDistrictName(i); } catch { }
                j.A().V(i).V(nome ?? ("District " + i)).V(di.m_populationData.m_finalCount).V(di.GetLandValue()).V(di.m_finalHappiness).V(di.m_finalCrimeRate)
                 .V(NomePolitica(di.m_specializationPolicies.ToString())).V(Mathf.RoundToInt(di.m_nameLocation.x)).V(Mathf.RoundToInt(di.m_nameLocation.z)).EA();
            }
            j.EA().P("parques", dm.m_parkCount);
            // --- limits of the game engine
            CitizenManager cm = Singleton<CitizenManager>.instance;
            j.K("limites").O()
             .K("predios").A().V(BM.m_buildingCount).V(BM.m_buildings.m_size).EA()
             .K("trechosDeRede").A().V(NM.m_segmentCount).V(NM.m_segments.m_size).EA()
             .K("nos").A().V(NM.m_nodeCount).V(NM.m_nodes.m_size).EA()
             .K("blocosDeZona").A().V(ZM.m_blockCount).V(ZM.m_blocks.m_size).EA()
             .K("veiculos").A().V(vm.m_vehicleCount).V(vm.m_vehicles.m_size).EA()
             .K("estacionados").A().V(vm.m_parkedCount).V(vm.m_parkedVehicles.m_size).EA()
             .K("cidadaos").A().V(cm.m_citizenCount).V(cm.m_citizens.m_size).EA()
             .K("pedestresAtivos").A().V(cm.m_instanceCount).V(cm.m_instances.m_size).EA()
             .K("arvores").A().V(Singleton<TreeManager>.instance.m_treeCount).V(Singleton<TreeManager>.instance.m_trees.m_size).EA()
             .K("linhas").A().V(tm.m_lineCount).V(tm.m_lines.m_size).EA()
             .K("distritos").A().V(dm.m_districtCount).V(dm.m_districts.m_size).EA().EO();
            return j.EO().ToString();
        }

        // ---------- map ----------
        static string terrenoCache; static string terrenoChave; static DateTime terrenoQuando;
        static string[] nomeRua; static uint[] nomeRuaBuild; static DateTime nomeRuaQuando;
        static string NomeDaRua(int i)
        {
            if (nomeRua == null || nomeRua.Length != NM.m_segments.m_size || (DateTime.UtcNow - nomeRuaQuando).TotalSeconds > 30)
            { nomeRua = new string[NM.m_segments.m_size]; nomeRuaBuild = new uint[NM.m_segments.m_size]; nomeRuaQuando = DateTime.UtcNow; }
            uint bi = NM.m_segments.m_buffer[i].m_buildIndex;
            if (nomeRua[i] == null || nomeRuaBuild[i] != bi)
            {
                string n = null;
                try { n = NM.GetSegmentName((ushort)i); } catch { }
                nomeRua[i] = n ?? ""; nomeRuaBuild[i] = bi;
            }
            return nomeRua[i];
        }

        static readonly ImmaterialResourceManager.Resource[] RECURSOS = {
            ImmaterialResourceManager.Resource.LandValue, ImmaterialResourceManager.Resource.NoisePollution, ImmaterialResourceManager.Resource.FireDepartment,
            ImmaterialResourceManager.Resource.PoliceDepartment, ImmaterialResourceManager.Resource.HealthCare, ImmaterialResourceManager.Resource.DeathCare,
            ImmaterialResourceManager.Resource.EducationElementary, ImmaterialResourceManager.Resource.EducationHighSchool, ImmaterialResourceManager.Resource.EducationUniversity,
            ImmaterialResourceManager.Resource.PublicTransport, ImmaterialResourceManager.Resource.Entertainment, ImmaterialResourceManager.Resource.CrimeRate };

        public static string Mapa()
        {
            ImmaterialResourceManager im = Singleton<ImmaterialResourceManager>.instance;
            NaturalResourceManager nrm = Singleton<NaturalResourceManager>.instance;
            TerrainManager tmn = Singleton<TerrainManager>.instance;
            // bounding box: everything the player built, with a margin
            float x1 = 1e9f, x2 = -1e9f, z1 = 1e9f, z2 = -1e9f; int cont = 0;
            for (int i = 1; i < BM.m_buildings.m_size; i++)
            {
                if ((BM.m_buildings.m_buffer[i].m_flags & Building.Flags.Created) == 0) continue;
                BuildingInfo info = BM.m_buildings.m_buffer[i].Info;
                if (info == null) continue;
                ItemClass.Service sv = info.m_class.m_service;
                if (sv != ItemClass.Service.Residential && sv != ItemClass.Service.Commercial && sv != ItemClass.Service.Industrial && sv != ItemClass.Service.Office && !(info.m_buildingAI is PlayerBuildingAI)) continue;
                if (info.m_buildingAI is OutsideConnectionAI) continue;
                Vector3 p = BM.m_buildings.m_buffer[i].m_position;
                x1 = Mathf.Min(x1, p.x); x2 = Mathf.Max(x2, p.x); z1 = Mathf.Min(z1, p.z); z2 = Mathf.Max(z2, p.z); cont++;
            }
            for (int i = 1; i < NM.m_segments.m_size; i++)
            {
                NetSegment s = NM.m_segments.m_buffer[i];
                if ((s.m_flags & NetSegment.Flags.Created) == 0 || !EhEstrada(s.Info) || (s.m_flags & NetSegment.Flags.Untouchable) != 0) continue;
                if (s.Info.name.IndexOf("Highway") >= 0) continue;
                Vector3 p = s.m_middlePosition;
                x1 = Mathf.Min(x1, p.x); x2 = Mathf.Max(x2, p.x); z1 = Mathf.Min(z1, p.z); z2 = Mathf.Max(z2, p.z); cont++;
            }
            if (cont == 0) { x1 = -960; x2 = 960; z1 = -960; z2 = 960; }
            float margem = 450f;
            x1 = Mathf.Max(-8640f, Mathf.Floor((x1 - margem) / 64f) * 64f); z1 = Mathf.Max(-8640f, Mathf.Floor((z1 - margem) / 64f) * 64f);
            x2 = Mathf.Min(8640f, Mathf.Ceil((x2 + margem) / 64f) * 64f); z2 = Mathf.Min(8640f, Mathf.Ceil((z2 + margem) / 64f) * 64f);

            JW j = new JW();
            j.O().P("carregado", true).K("caixa").A().V(x1).V(z1).V(x2).V(z2).EA();
            // terrain: heights (0-255) and water mask; rebuilt every 5 min or when the box changes
            string chave = x1 + "," + z1 + "," + x2 + "," + z2;
            if (terrenoCache == null || terrenoChave != chave || (DateTime.UtcNow - terrenoQuando).TotalSeconds > 300)
            {
                float passo = Mathf.Max(16f, Mathf.Ceil(Mathf.Max(x2 - x1, z2 - z1) / 300f / 8f) * 8f);
                int nx = (int)((x2 - x1) / passo) + 1, nz = (int)((z2 - z1) / passo) + 1;
                float[] h = new float[nx * nz]; byte[] agua = new byte[nx * nz];
                float hmin = 1e9f, hmax = -1e9f;
                for (int b = 0; b < nz; b++)
                    for (int a = 0; a < nx; a++)
                    {
                        Vector3 p = new Vector3(x1 + a * passo, 0, z1 + b * passo);
                        float hh = tmn.SampleRawHeightSmooth(p);
                        h[b * nx + a] = hh; hmin = Mathf.Min(hmin, hh); hmax = Mathf.Max(hmax, hh);
                        agua[b * nx + a] = (byte)(tmn.HasWater(new Vector2(p.x, p.z)) ? 1 : 0);
                    }
                byte[] hb = new byte[nx * nz];
                for (int k = 0; k < hb.Length; k++) hb[k] = (byte)Mathf.Clamp(Mathf.RoundToInt((h[k] - hmin) / Mathf.Max(1f, hmax - hmin) * 255f), 0, 255);
                JW t = new JW();
                t.O().P("passo", passo).P("nx", nx).P("nz", nz).P("hmin", hmin).P("hmax", hmax).P("alturas", Convert.ToBase64String(hb)).P("agua", Convert.ToBase64String(agua)).K("recursos").Raw(Recursos(x1, z1, x2, z2)).EO();
                terrenoCache = t.ToString(); terrenoChave = chave; terrenoQuando = DateTime.UtcNow;
            }
            j.K("terreno").Raw(terrenoCache);
            // purchased tiles (5x5 grid, or 9x9 with the 81 Tiles mod)
            GameAreaManager gam = Singleton<GameAreaManager>.instance;
            int lado = gam.MaxAreaCount > 25 ? 9 : 5;
            j.K("lotes").O().P("lado", lado).K("comprados").A();
            for (int z = 0; z < lado; z++) for (int x = 0; x < lado; x++) { bool u = false; try { u = gam.IsUnlocked(x, z); } catch { } if (u) j.A().V(x).V(z).EA(); }
            j.EA().EO();
            // networks
            List<string> tipos = new List<string>(); Dictionary<string, int> tipoIx = new Dictionary<string, int>();
            List<string> ruas = new List<string>(); Dictionary<string, int> ruaIx = new Dictionary<string, int>();
            JW js = new JW(); js.A();
            for (int i = 1; i < NM.m_segments.m_size; i++)
            {
                NetSegment s = NM.m_segments.m_buffer[i];
                if ((s.m_flags & NetSegment.Flags.Created) == 0 || s.Info == null) continue;
                ItemClass.Service sv = s.Info.m_class.m_service;
                if (sv != ItemClass.Service.Road && sv != ItemClass.Service.PublicTransport && sv != ItemClass.Service.Water && sv != ItemClass.Service.Electricity && sv != ItemClass.Service.Beautification) continue;
                string nm = s.Info.name;
                if (nm.IndexOf("Airplane") >= 0 || nm.IndexOf("Ship") >= 0 || nm.IndexOf("Line") >= 0 || nm.IndexOf("Connection") >= 0) continue;
                Vector3 a = NM.m_nodes.m_buffer[s.m_startNode].m_position, b = NM.m_nodes.m_buffer[s.m_endNode].m_position, m = s.m_middlePosition;
                bool fora = (a.x < x1 && b.x < x1) || (a.x > x2 && b.x > x2) || (a.z < z1 && b.z < z1) || (a.z > z2 && b.z > z2);
                if (fora && sv != ItemClass.Service.Road && sv != ItemClass.Service.PublicTransport) continue;   // highways and rails go all the way to the map edge
                int ix;
                if (!tipoIx.TryGetValue(nm, out ix)) { ix = tipos.Count; tipoIx[nm] = ix; tipos.Add(nm + "|" + sv + "|" + s.Info.m_halfWidth.ToString("0.#", CultureInfo.InvariantCulture)); }
                js.A().V(Mathf.RoundToInt(a.x)).V(Mathf.RoundToInt(a.z)).V(Mathf.RoundToInt(m.x)).V(Mathf.RoundToInt(m.z)).V(Mathf.RoundToInt(b.x)).V(Mathf.RoundToInt(b.z)).V(ix).V(s.m_trafficDensity).V(i);
                int ri = -1;
                if (sv == ItemClass.Service.Road)
                {
                    string rua = NomeDaRua(i);
                    if (!string.IsNullOrEmpty(rua) && !ruaIx.TryGetValue(rua, out ri)) { ri = ruas.Count; ruaIx[rua] = ri; ruas.Add(rua); }
                    if (string.IsNullOrEmpty(rua)) ri = -1;
                }
                js.V(ri).EA();
            }
            js.EA();
            j.K("ruas").A(); foreach (string t in ruas) j.V(t); j.EA();
            j.K("tiposRede").A(); foreach (string t in tipos) j.V(t); j.EA();
            j.K("redes").Raw(js.ToString());
            // buildings
            List<string> classes = new List<string>(); Dictionary<string, int> classeIx = new Dictionary<string, int>();
            List<string> nomes = new List<string>(); Dictionary<string, int> nomeIx = new Dictionary<string, int>();
            List<string> probs = new List<string>(); Dictionary<string, int> probIx = new Dictionary<string, int>();
            probs.Add(""); probIx[""] = 0;
            DistrictManager dmp = Singleton<DistrictManager>.instance;
            JW jb = new JW(); jb.A();
            for (int i = 1; i < BM.m_buildings.m_size; i++)
            {
                Building b = BM.m_buildings.m_buffer[i];
                if ((b.m_flags & Building.Flags.Created) == 0 || b.Info == null) continue;
                BuildingInfo info = b.Info;
                ItemClass.Service sv = info.m_class.m_service;
                bool zonado = sv == ItemClass.Service.Residential || sv == ItemClass.Service.Commercial || sv == ItemClass.Service.Industrial || sv == ItemClass.Service.Office;
                if (!zonado && !(info.m_buildingAI is PlayerBuildingAI)) continue;
                if (info.m_buildingAI is OutsideConnectionAI) continue;
                string nm = info.name;
                if (!zonado && (nm.IndexOf("Pole") >= 0 || nm.IndexOf("Junction") >= 0 || nm.IndexOf("Pillar") >= 0 || nm.IndexOf("Connection") >= 0)) continue;
                Vector3 p = b.m_position;
                if (p.x < x1 || p.x > x2 || p.z < z1 || p.z > z2) continue;
                string cl = sv + "/" + info.m_class.m_subService;
                int ci; if (!classeIx.TryGetValue(cl, out ci)) { ci = classes.Count; classeIx[cl] = ci; classes.Add(cl); }
                int ni = -1;
                if (!zonado) { if (!nomeIx.TryGetValue(nm, out ni)) { ni = nomes.Count; nomeIx[nm] = ni; nomes.Add(Titulo(info)); } }
                string ps = b.m_problems.IsNone ? "" : b.m_problems.ToString();
                if ((b.m_flags & Building.Flags.Abandoned) != 0) ps = ps.Length > 0 ? ps + ", Abandoned" : "Abandoned";
                if ((b.m_flags & Building.Flags.BurnedDown) != 0) ps = ps.Length > 0 ? ps + ", BurnedDown" : "BurnedDown";
                int pi; if (!probIx.TryGetValue(ps, out pi)) { pi = probs.Count; probIx[ps] = pi; probs.Add(ps); }
                byte pol; nrm.CheckPollution(p, out pol);
                jb.A().V(Mathf.RoundToInt(p.x)).V(Mathf.RoundToInt(p.z)).V(Mathf.RoundToInt(b.m_angle * 100f)).V(b.Width).V(b.Length).V(ci).V((int)info.m_class.m_level + 1).V(pi).V(ni).V(pol).V(b.m_happiness).V(b.m_health).V(b.m_citizenCount);
                for (int r = 0; r < RECURSOS.Length; r++) { int v; im.CheckLocalResource(RECURSOS[r], p, out v); jb.V(v); }
                jb.V(b.m_garbageBuffer).V(dmp.GetDistrict(p)).V(i).EA();
            }
            jb.EA();
            j.K("classes").A(); foreach (string t in classes) j.V(t); j.EA();
            j.K("nomes").A(); foreach (string t in nomes) j.V(t); j.EA();
            j.K("problemas").A(); foreach (string t in probs) j.V(t); j.EA();
            j.K("camposPredio").A();
            foreach (string c in new string[] { "x", "z", "ang", "larg", "comp", "classe", "nivel", "problema", "nome", "poluicao", "felicidade", "saude", "moradores",
                "valorTerreno", "ruido", "bombeiros", "policia", "saudeCob", "funeraria", "fundamental", "medio", "superior", "transporte", "lazer", "crime", "lixo", "distrito", "id" }) j.V(c);
            j.EA().K("predios").Raw(jb.ToString());
            // zoned cells that are still empty: x, z, angle*100, zone (flat, 4 numbers per cell)
            j.K("zonasVazias").A();
            for (int i = 1; i < ZM.m_blocks.m_size; i++)
            {
                if ((ZM.m_blocks.m_buffer[i].m_flags & 1u) == 0) continue;
                ZoneBlock zb = ZM.m_blocks.m_buffer[i];
                Vector3 zp = zb.m_position;
                if (zp.x < x1 || zp.x > x2 || zp.z < z1 || zp.z > z2) continue;
                ulong ocup = zb.m_occupied1 | zb.m_occupied2;
                int rows = zb.RowCount;
                float vx = Mathf.Cos(zb.m_angle) * 8f, vz = Mathf.Sin(zb.m_angle) * 8f;
                int ang = Mathf.RoundToInt(zb.m_angle * 100f);
                for (int z = 0; z < rows; z++)
                    for (int x = 0; x < 4; x++)
                    {
                        ulong bit = 1UL << ((z << 3) | x);
                        if ((zb.m_valid & bit) == 0 || (zb.m_shared & bit) != 0 || (ocup & bit) != 0) continue;
                        int zona = (int)zb.GetZone(x, z);
                        if (zona <= 1) continue;   // 0 = none, 1 = unzoned
                        float cx = zp.x + (x - 3.5f) * vx + (z - 3.5f) * vz, cz = zp.z + (x - 3.5f) * vz - (z - 3.5f) * vx;
                        j.V(Mathf.RoundToInt(cx)).V(Mathf.RoundToInt(cz)).V(ang).V(zona);
                    }
            }
            j.EA();
            // district and park/industry areas (32 m grid), only if any exists
            {
                float gp = 32f;
                int gx = (int)((x2 - x1) / gp) + 1, gz = (int)((z2 - z1) / gp) + 1;
                byte[] gd = new byte[gx * gz], gk = new byte[gx * gz];
                bool temD = false, temP = false;
                for (int b = 0; b < gz; b++)
                    for (int a = 0; a < gx; a++)
                    {
                        Vector3 p = new Vector3(x1 + a * gp, 0, z1 + b * gp);
                        byte di = dmp.GetDistrict(p), pk = dmp.GetPark(p);
                        gd[b * gx + a] = di; gk[b * gx + a] = pk;
                        if (di != 0) temD = true;
                        if (pk != 0) temP = true;
                    }
                j.K("gradeDistritos").O().P("passo", gp).P("nx", gx).P("nz", gz);
                if (temD) j.P("distritos", Convert.ToBase64String(gd));
                if (temP) j.P("parques", Convert.ToBase64String(gk));
                j.EO();
                j.K("areas").A();
                if (temP)
                    for (int i = 1; i < dmp.m_parks.m_size; i++)
                    {
                        DistrictPark pk = dmp.m_parks.m_buffer[i];
                        if ((pk.m_flags & DistrictPark.Flags.Created) == 0) continue;
                        string nome = null; try { nome = dmp.GetParkName(i); } catch { }
                        j.A().V(i).V(nome ?? ("Area " + i)).V(pk.m_parkType.ToString()).EA();
                    }
                j.EA();
            }
            // transport lines (stops in order)
            TransportManager tm = Singleton<TransportManager>.instance;
            j.K("linhas").A();
            for (int i = 1; i < tm.m_lines.m_size; i++)
            {
                TransportLine tl = tm.m_lines.m_buffer[i];
                if ((tl.m_flags & TransportLine.Flags.Created) == 0 || (tl.m_flags & (TransportLine.Flags.Temporary | TransportLine.Flags.Hidden)) != 0 || tl.Info == null) continue;
                string corHex = "#3b79a8"; List<int> pts = new List<int>();
                try
                {
                    Color32 cor = tm.GetLineColor((ushort)i);
                    corHex = "#" + cor.r.ToString("x2") + cor.g.ToString("x2") + cor.b.ToString("x2");
                    ushort parada = tl.m_stops; int guarda = 0;
                    while (parada != 0 && guarda++ < 400)
                    {
                        Vector3 p = NM.m_nodes.m_buffer[parada].m_position;
                        pts.Add(Mathf.RoundToInt(p.x)); pts.Add(Mathf.RoundToInt(p.z));
                        parada = TransportLine.GetNextStop(parada);
                        if (parada == tl.m_stops) break;
                    }
                }
                catch { }
                j.A().V(tl.Info.m_transportType.ToString()).V(corHex).A();
                foreach (int v in pts) j.V(v);
                j.EA().EA();
            }
            j.EA();
            // districts (labels) and outside connections
            DistrictManager dm = Singleton<DistrictManager>.instance;
            j.K("distritos").A();
            for (int i = 1; i < dm.m_districts.m_size; i++)
            {
                District di = dm.m_districts.m_buffer[i];
                if ((di.m_flags & District.Flags.Created) == 0) continue;
                string nome = null; try { nome = dm.GetDistrictName(i); } catch { }
                j.A().V(nome ?? ("District " + i)).V(Mathf.RoundToInt(di.m_nameLocation.x)).V(Mathf.RoundToInt(di.m_nameLocation.z)).V(i).EA();
            }
            j.EA();
            return j.EO().ToString();
        }

        /// Slice of the game's natural resource grid (33.75 m cells): ore, oil, fertile land, forest, trees, ground pollution.
        static string Recursos(float x1, float z1, float x2, float z2)
        {
            NaturalResourceManager.ResourceCell[] cel = Singleton<NaturalResourceManager>.instance.m_naturalResources;
            int ax = Mathf.Clamp((int)(x1 / 33.75f + 256f), 0, 511), bx = Mathf.Clamp((int)(x2 / 33.75f + 256f), 0, 511);
            int az = Mathf.Clamp((int)(z1 / 33.75f + 256f), 0, 511), bz = Mathf.Clamp((int)(z2 / 33.75f + 256f), 0, 511);
            int nx = bx - ax + 1, nz = bz - az + 1;
            byte[] ore = new byte[nx * nz], oil = new byte[nx * nz], fer = new byte[nx * nz], flo = new byte[nx * nz], arv = new byte[nx * nz], pol = new byte[nx * nz];
            for (int z = 0; z < nz; z++)
                for (int x = 0; x < nx; x++)
                {
                    NaturalResourceManager.ResourceCell c = cel[(az + z) * 512 + ax + x];
                    int k = z * nx + x;
                    ore[k] = c.m_ore; oil[k] = c.m_oil; fer[k] = c.m_fertility; flo[k] = c.m_forest; arv[k] = c.m_tree; pol[k] = c.m_pollution;
                }
            JW j = new JW();
            j.O().P("passo", 33.75).P("x0", (ax - 256) * 33.75).P("z0", (az - 256) * 33.75).P("nx", nx).P("nz", nz)
             .P("minerio", Convert.ToBase64String(ore)).P("petroleo", Convert.ToBase64String(oil)).P("fertil", Convert.ToBase64String(fer))
             .P("floresta", Convert.ToBase64String(flo)).P("arvores", Convert.ToBase64String(arv)).P("poluicao", Convert.ToBase64String(pol)).EO();
            return j.ToString();
        }

        static string NomePolitica(string nomes)
        {
            if (string.IsNullOrEmpty(nomes) || nomes == "None") return "";
            List<string> r = new List<string>();
            foreach (string parte in nomes.Split(','))
            {
                string n = parte.Trim(), t = n;
                try { if (Locale.Exists("POLICIES", n)) t = Locale.Get("POLICIES", n); } catch { }
                r.Add(t);
            }
            return string.Join(", ", r.ToArray());
        }

        static string Titulo(BuildingInfo info)
        {
            try { if (Locale.Exists("BUILDING_TITLE", info.name)) return Locale.Get("BUILDING_TITLE", info.name); } catch { }
            return info.name;
        }

        // ---------- list of service buildings, with the text the game itself shows ----------
        public static string Servicos()
        {
            JW j = new JW();
            j.O().P("carregado", true).K("predios").A();
            for (int i = 1; i < BM.m_buildings.m_size; i++)
            {
                Building b = BM.m_buildings.m_buffer[i];
                if ((b.m_flags & Building.Flags.Created) == 0 || b.Info == null) continue;
                BuildingInfo info = b.Info;
                if (!(info.m_buildingAI is PlayerBuildingAI) || info.m_buildingAI is OutsideConnectionAI) continue;
                string nm = info.name;
                if (nm.IndexOf("Pole") >= 0 || nm.IndexOf("Junction") >= 0 || nm.IndexOf("Pillar") >= 0 || nm.IndexOf("Connection") >= 0) continue;
                if ((b.m_flags & Building.Flags.Untouchable) != 0 && b.m_parentBuilding != 0) continue;   // sub-buildings
                string stats = "";
                try { stats = info.m_buildingAI.GetLocalizedStats((ushort)i, ref BM.m_buildings.m_buffer[i]) ?? ""; } catch { }
                int vagas = 0;
                for (int k = 0; k < 4; k++)
                {
                    FieldInfo f = info.m_buildingAI.GetType().GetField("m_workPlaceCount" + k);
                    if (f != null) vagas += Convert.ToInt32(f.GetValue(info.m_buildingAI));
                }
                j.A().V(i).V(Titulo(info)).V(info.m_class.m_service.ToString()).V(Mathf.RoundToInt(b.m_position.x)).V(Mathf.RoundToInt(b.m_position.z))
                 .V(b.m_problems.IsNone ? "" : b.m_problems.ToString()).V(stats).V(Mathf.RoundToInt(info.m_buildingAI.GetMaintenanceCost() * 0.0016f)).V(vagas)
                 .V((b.m_flags & Building.Flags.Active) != 0).EA();
            }
            return j.EA().EO().ToString();
        }
    }
}
