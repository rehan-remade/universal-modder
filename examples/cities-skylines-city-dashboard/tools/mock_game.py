#!/usr/bin/env python3
"""Serve the dashboard page with a synthetic city, so it can be opened and tested without the game.

    python3 tools/mock_game.py                 # http://127.0.0.1:19681, page assembled from web/src
    python3 tools/mock_game.py --port 8000 --web path/to/web

It answers the same routes as the mod (/, /api/cidade, /api/mapa, /api/servicos, /api/historico, /api/dianoite)
in the same wire format. Every number here is made up by this script: no game data is involved. The city is
deterministic (fixed seed) and the clock, traffic and day/night samples move a little on every request, so the
page's live refresh has something to show.
"""
import argparse, base64, glob, json, math, os, random, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = ["x", "z", "ang", "larg", "comp", "classe", "nivel", "problema", "nome", "poluicao", "felicidade", "saude", "moradores",
          "valorTerreno", "ruido", "bombeiros", "policia", "saudeCob", "funeraria", "fundamental", "medio", "superior",
          "transporte", "lazer", "crime", "lixo", "distrito", "id"]
CLASSES = ["Residential/ResidentialLow", "Residential/ResidentialHigh", "Commercial/CommercialLow", "Commercial/CommercialHigh",
           "Industrial/IndustrialGeneric", "Office/OfficeGeneric", "Beautification/None", "Electricity/None", "Water/None",
           "Garbage/None", "HealthCare/None", "FireDepartment/None", "PoliceDepartment/None", "Education/None",
           "PublicTransport/PublicTransportBus", "Monument/None"]
# service buildings placed on the map: (class index, name, weekly upkeep, jobs, coverage field, radius)
SERVICES = [(7, "Wind Turbine", 80, 0, None, 0), (7, "Solar Power Plant", 1200, 40, None, 0), (8, "Water Pumping Station", 320, 0, None, 0),
            (8, "Water Drain Pipe", 320, 0, None, 0), (9, "Incineration Plant", 1440, 30, None, 0), (9, "Landfill Site", 480, 12, None, 0),
            (10, "Medical Clinic", 400, 33, "saudeCob", 900), (10, "Crematorium", 720, 30, "funeraria", 1000),
            (11, "Fire House", 560, 31, "bombeiros", 800), (12, "Police Station", 480, 40, "policia", 800),
            (13, "Elementary School", 160, 26, "fundamental", 600), (13, "High School", 560, 100, "medio", 1300),
            (13, "University", 1920, 126, "superior", 1500), (6, "Small Park", 8, 0, "lazer", 350), (6, "Plaza with Trees", 24, 0, "lazer", 400),
            (14, "Bus Depot", 640, 20, None, 0), (15, "Statue of Industry", 320, 0, "lazer", 500)]
PROBLEMS = ["", "Garbage", "Death", "Noise", "Crime", "Pollution", "NoGoods", "Death, MajorProblem", "Garbage, MajorProblem", "Water", "Abandoned"]
STREETS = ["Harbor", "Mill", "Orchard", "Station", "Foundry", "Canal", "Quarry", "Linden", "Market", "Beacon", "Tanner", "Willow"]


def b64(values):
    return base64.b64encode(bytes(max(0, min(255, int(v))) for v in values)).decode()


class City:
    def __init__(self, seed=7):
        r = self.r = random.Random(seed)
        self.t0 = time.time()
        self.box = [-1600, -1408, 1600, 1408]
        x1, z1, x2, z2 = self.box
        self.river = lambda x: -1050 + 180 * math.sin(x / 520.0)          # centre line of the river (z)
        self.is_water = lambda x, z: abs(z - self.river(x)) < 95
        # road grid: avenues every 480 m, streets every 160 m (x) and 112 m (z), north of the river
        self.kinds = ["Basic Road|Road|8", "Medium Road|Road|16", "Highway|Road|11", "Train Track|PublicTransport|5",
                      "Water Pipe|Water|4.5", "Pedestrian Pavement|Beautification|3", "HighwayRamp|Road|6"]
        xs = list(range(-1280, 1281, 160)); zs = list(range(-784, 1121, 112))
        self.segs, self.streets = [], []
        sid = 0

        def seg(ax, az, bx, bz, kind, name=None, dens=None):
            nonlocal sid
            sid += 1
            if name is not None and name not in self.streets:
                self.streets.append(name)
            d = dens if dens is not None else (r.randint(0, 35) if kind == 0 else r.randint(15, 95) if kind == 1 else r.randint(5, 60))
            self.segs.append([ax, az, (ax + bx) // 2, (az + bz) // 2, bx, bz, kind, d, sid, self.streets.index(name) if name is not None else -1])

        for i, x in enumerate(xs):
            av = i % 3 == 0
            for a, b in zip(zs, zs[1:]):
                seg(x, a, x, b, 1 if av else 0, STREETS[i % len(STREETS)] + (" Avenue" if av else " Street"))
        for j, z in enumerate(zs):
            av = j % 4 == 0
            for a, b in zip(xs, xs[1:]):
                seg(a, z, b, z, 1 if av else 0, STREETS[(j + 5) % len(STREETS)] + (" Boulevard" if av else " Road"))
        for a in range(-4000, 4000, 400):                                   # highway south of the river, edge to edge
            seg(a, -1300, a + 400, -1300 + (40 if a % 800 == 0 else -40), 2, "Riverside Highway", r.randint(10, 70))
        seg(0, -1300, 0, -1000, 6, None, 82); seg(0, -1000, 0, -784, 1, "Harbor Avenue", 91)     # ramp and bridge into town
        for a in range(-4000, 4000, 500):
            seg(a, 1300, a + 500, 1300, 3)
        for x in xs[::2]:
            seg(x, zs[0], x, zs[-1], 4)
        # buildings: lots along both sides of every block
        self.buildings, self.names, bid = [], [], 0
        centre = lambda x, z: math.hypot(x / 1300.0, (z - 170) / 950.0)
        for bx in xs[:-1]:
            for bz in zs[:-1]:
                for row, zz in ((0, bz + 30), (1, bz + 82)):
                    x = bx + 28
                    while x < bx + 140:
                        w = r.choice([2, 2, 3, 4]); d = r.choice([2, 3])
                        cx = x + w * 4
                        if cx + w * 4 > bx + 148:
                            break
                        c = centre(cx, zz)
                        if r.random() < 0.10 + 0.5 * max(0, c - 0.75):       # empty lot
                            x += w * 8 + 2
                            continue
                        east = cx > 800
                        cls = (4 if east and r.random() < 0.8 else 5 if c < 0.3 and r.random() < 0.5 else 3 if c < 0.4 and r.random() < 0.35
                               else 2 if r.random() < 0.08 else 1 if c < 0.55 else 0)
                        bid += 1
                        self.buildings.append({"x": int(cx), "z": int(zz), "ang": 0 if row else 314, "w": w, "d": d, "cls": cls,
                                               "lvl": 1 + min(4 if cls < 2 else 2, int(r.random() * (5 if cls < 2 else 3) * (1.25 - min(1, c)))), "id": bid, "svc": None})
                        x += w * 8 + 2
        # service buildings replace random lots
        self.services = []
        for cls, name, upkeep, jobs, field, radius in SERVICES:
            n = {"Wind Turbine": 6, "Small Park": 14, "Plaza with Trees": 6, "Elementary School": 5, "Medical Clinic": 3, "Fire House": 3,
                 "Police Station": 2, "Crematorium": 1, "Incineration Plant": 2}.get(name, 1)
            for _ in range(n):
                b = r.choice(self.buildings)
                while b["svc"] or (field == "funeraria" and b["x"] > -400):       # the one crematorium sits in the west: the east is out of reach
                    b = r.choice(self.buildings)
                if name not in self.names:
                    self.names.append(name)
                b.update(cls=cls, lvl=1, svc=(name, upkeep, jobs, field, radius), w=min(4, b["w"] + 1))
                self.services.append(b)
        self.lines = [["Bus", "#e34948", [-1120, -112, -640, -112, -160, 112, 320, 112, 640, 448, 160, 560, -480, 336]],
                      ["Metro", "#6250d6", [-960, 784, -320, 448, 320, 112, 960, -224]]]
        self.districts = [["Old Town", -480, 300, 1], ["Foundry Row", 1040, 200, 2], ["Linden Heights", -800, 900, 3]]
        self.district_of = lambda x, z: 2 if x > 800 else 1 if (abs(x + 480) < 520 and abs(z - 300) < 380) else 3 if (x < -300 and z > 700) else 0
        for b in self.buildings:
            self._score(b)

    def _score(self, b):
        r, x, z = self.r, b["x"], b["z"]
        cov = {k: 0 for k in ("saudeCob", "funeraria", "bombeiros", "policia", "fundamental", "medio", "superior", "lazer")}
        for s in self.services:
            _, _, _, field, radius = s["svc"]
            if field:
                d = math.hypot(x - s["x"], z - s["z"])
                if d < radius:
                    cov[field] += int((1 - d / radius) * 220)
        stop = min(math.hypot(x - p[i], z - p[i + 1]) for _, _, p in self.lines for i in range(0, len(p), 2))
        pol = int(max(0, 255 - min(math.hypot(x - o["x"], z - o["z"]) for o in self.buildings if o["cls"] == 4) * 1.6)) if any(o["cls"] == 4 for o in self.buildings) else 0
        zoned = b["cls"] < 6
        prob = 0
        if zoned:
            if cov["funeraria"] == 0 and r.random() < 0.10:
                prob = 7 if r.random() < 0.3 else 2
            elif pol > 120 and b["cls"] < 2:
                prob = 5
            elif r.random() < 0.02:
                prob = r.choice([1, 3, 4, 6, 8, 9])
        b["row"] = [x, z, b["ang"], b["w"], b["d"], b["cls"], b["lvl"], prob, self.names.index(b["svc"][0]) if b["svc"] else -1, pol,
                    max(20, 92 - pol // 6 - (15 if prob else 0) + r.randint(-8, 6)), max(30, 88 - pol // 5 + r.randint(-6, 6)),
                    (r.randint(8, 60) if b["cls"] == 1 else r.randint(2, 6)) if b["cls"] < 2 else r.randint(4, 30),
                    max(3, int(70 - 45 * math.hypot(x / 1300.0, (z - 170) / 950.0) + cov["lazer"] / 20 - pol / 8)), r.randint(0, 40) + (90 if abs(x) % 480 < 60 else 0),
                    cov["bombeiros"], cov["policia"], cov["saudeCob"], cov["funeraria"], cov["fundamental"], cov["medio"], cov["superior"],
                    int(max(0, 300 - stop) * 0.9) if stop < 300 else 0, cov["lazer"], r.randint(0, 12) + (0 if cov["policia"] else 18),
                    r.randint(0, 400) + (2600 if prob in (1, 8) else 0), self.district_of(x, z), b["id"]]

    # ---------- routes ----------
    def weeks(self):
        return int((time.time() - self.t0) / 4)

    def date(self, back=0):
        days = (self.weeks() - back) * 7 + 400 * 7
        y, d = 2030 + days // 364, days % 364
        return "%04d-%02d-%02d" % (y, d // 28 % 12 + 1, d % 28 + 1)

    def terrain(self):
        if getattr(self, "_terrain", None):
            return self._terrain
        x1, z1, x2, z2 = self.box
        step = 32
        nx, nz = (x2 - x1) // step + 1, (z2 - z1) // step + 1
        h, w = [], []
        for j in range(nz):
            for i in range(nx):
                x, z = x1 + i * step, z1 + j * step
                h.append(90 + 80 * math.sin(x / 700.0) * math.cos(z / 520.0) + 40 * math.sin((x + z) / 260.0))
                w.append(1 if self.is_water(x, z) else 0)
        rs = 33.75
        rnx, rnz = int((x2 - x1) / rs) + 1, int((z2 - z1) / rs) + 1
        grid = lambda fn: b64(fn(x1 + i * rs, z1 + j * rs) for j in range(rnz) for i in range(rnx))
        blob = lambda cx, cz, rad: (lambda x, z: 0 if self.is_water(x, z) else max(0, 230 - math.hypot(x - cx, z - cz) / rad * 230))
        ind = [b for b in self.buildings if b["cls"] == 4]
        res = {"passo": rs, "x0": x1, "z0": z1, "nx": rnx, "nz": rnz, "minerio": grid(blob(1100, 900, 500)), "petroleo": grid(lambda x, z: 0),
               "fertil": grid(blob(-900, -300, 900)), "floresta": grid(blob(-1200, 1100, 600)), "arvores": grid(blob(-1200, 1100, 500)),
               "poluicao": grid(lambda x, z: max(0, 255 - min(math.hypot(x - o["x"], z - o["z"]) for o in ind) * 1.6) if ind else 0)}
        gs = 32
        gnx, gnz = (x2 - x1) // gs + 1, (z2 - z1) // gs + 1
        self._terrain = ({"passo": step, "nx": nx, "nz": nz, "hmin": 10, "hmax": 265, "alturas": b64(h), "agua": b64(w), "recursos": res},
                         {"passo": gs, "nx": gnx, "nz": gnz, "distritos": b64(self.district_of(x1 + i * gs, z1 + j * gs) for j in range(gnz) for i in range(gnx))})
        return self._terrain

    def mapa(self):
        terrain, grid = self.terrain()
        wob = math.sin(time.time() / 3.0)
        segs = [s[:7] + [max(0, min(100, int(s[7] + wob * 8)))] + s[8:] for s in self.segs]
        empties = []
        for bx in range(-1280, 1280, 160):
            if bx % 320 == 0:
                for k in range(6):
                    empties += [bx + 36 + k * 8, 1150, 0, 3 if bx < 0 else 6]
        return {"carregado": True, "caixa": self.box,
                "terreno": terrain,
                "lotes": {"lado": 5, "comprados": [[2, 2], [1, 2], [2, 1]]}, "ruas": self.streets, "tiposRede": self.kinds, "redes": segs,
                "classes": CLASSES, "nomes": self.names, "problemas": PROBLEMS, "camposPredio": FIELDS, "predios": [b["row"] for b in self.buildings],
                "zonasVazias": empties,
                "gradeDistritos": grid,
                "areas": [], "linhas": self.lines, "distritos": self.districts}

    def cidade(self):
        B = [b["row"] for b in self.buildings]
        res = [r for r in B if r[5] < 2]
        pop = sum(r[12] for r in res) * 3 + self.weeks() * 3
        jobs = {"comercial": 2100, "industrial": 1500, "escritorios": 2600, "publico": 900}
        sector = lambda total, free, n, hap, lv: {"total": total, "ocupados": total - free, "vazios": free, "predios": n, "abandonados": 0, "queimados": 0,
                                                  "desabados": 0, "saude": 80, "felicidade": hap, "crime": 6, "nivelMedio": 0, "area": n * 9, "niveis": lv}
        count = lambda c: sum(1 for r in B if r[5] in c)
        probs = {}
        for r in B:
            for p in [q.strip() for q in PROBLEMS[r[7]].split(",") if q.strip() and "Problem" not in q]:
                e = probs.setdefault(p, [0, 0, 0]); e[0] += 1; e[1] += "Major" in PROBLEMS[r[7]]
        roads = [s for s in self.segs if s[6] in (0, 1, 2, 6)]
        worst = sorted(roads, key=lambda s: -s[7])[:25]
        unemployed = int(pop * 0.055)
        return {"carregado": True,
                "geral": {"cidade": "Mockville", "data": self.date(), "pausado": False, "velocidade": 3, "diasPorSegundo": 1.75, "lotes": 3, "lotesMax": 25},
                "dinheiro": {"caixa": 412300 + self.weeks() * 2150, "receita": 41200, "despesa": 39050,
                             "porServico": {"Residential": [22900, 0], "Commercial": [7400, 0], "Industrial": [3100, 0], "Office": [6100, 0], "Citizen": [1200, 0], "Tourism": [500, 0],
                                            "Road": [0, 2900], "Electricity": [0, 3400], "Water": [0, 2100], "Garbage": [0, 4300], "HealthCare": [0, 5200], "FireDepartment": [0, 2400],
                                            "PoliceDepartment": [0, 2300], "Education": [0, 11800], "Beautification": [0, 900], "Monument": [0, 650], "PublicTransport": [1900, 3100]},
                             "impostos": {"ResidencialBaixa": 9, "ResidencialAlta": 10, "ComercialBaixa": 11, "ComercialAlta": 12, "Industria": 11, "Escritorios": 10},
                             "orcamento": {k: [100, 100] for k in ("Electricity", "Water", "HealthCare", "FireDepartment", "PoliceDepartment", "Road", "Beautification", "Monument")} | {"Garbage": [100, 80], "Education": [105, 95]},
                             "politicas": ["Recycling", "Smoke Detector Distribution"]},
                "demanda": {"r": 62, "c": 38, "w": 21, "rAtual": 60, "cAtual": 40, "wAtual": 20, "ajusteImpostoR": 0, "ajusteImpostoC": -2, "ajusteImpostoW": 0,
                            "empregos": sum(jobs.values()), "vagasLivres": 310, "desempregados": unemployed},
                "populacao": {"total": pop, "idades": [int(pop * f) for f in (0.08, 0.13, 0.19, 0.38, 0.22)], "nascimentos": 61, "mortes": 44, "expectativa": 78, "felicidade": 81,
                              "desempregoPct": 6, "trabalhadores": 6800, "postos": sum(jobs.values()),
                              "semEstudo": {"pessoas": int(pop * 0.17), "aptos": 800, "desempregados": 25, "semTeto": 0}, "fundamental": {"pessoas": int(pop * 0.22), "aptos": 1400, "desempregados": 40, "semTeto": 0},
                              "medio": {"pessoas": int(pop * 0.31), "aptos": 2300, "desempregados": 75, "semTeto": 0}, "superior": {"pessoas": int(pop * 0.30), "aptos": 2700, "desempregados": unemployed - 140, "semTeto": 0},
                              "turistas": [140, 90, 35], "visitasTuristas": [60, 44, 20]},
                "setores": {"residencial": sector(5200, 260, count((0, 1)), 84, [9, 16, 25, 30, 20]), "comercial": sector(jobs["comercial"], 60, count((2, 3)), 74, [35, 40, 25, 0, 0]),
                            "industrial": sector(jobs["industrial"], 110, count((4,)), 88, [82, 14, 4, 0, 0]), "escritorios": sector(jobs["escritorios"], 95, count((5,)), 79, [40, 38, 22, 0, 0]),
                            "publico": sector(jobs["publico"], 45, len(self.services), 0, [100, 0, 0, 0, 0]), "visitantes": sector(900, 300, 0, 0, [100, 0, 0, 0, 0])},
                "zonas": {"ResidentialLow": [4100, 310], "ResidentialHigh": [2600, 190], "CommercialLow": [600, 20], "CommercialHigh": [900, 12], "Industrial": [1500, 220], "Office": [1800, 36]},
                "infra": {"energia": [41200, 46000], "aquecimento": [0, 0], "agua": [118000, 160000], "esgoto": [117000, 180000], "reservaAgua": [0, 0], "poluicaoAgua": 0,
                          "lixo": {"acumulado": 384000, "capacidadeAterros": 400000, "producaoSemanal": 58000, "incineracaoSemanal": 61440, "pilhas": 1}},
                "servicos": {"saude": {"capacidadeTratamento": 300, "doentes": 190, "hospitais": 3, "saudeMedia": 79},
                             "funeraria": {"corposAguardando": probs.get("Death", [0])[0] * 3, "sepultados": 0, "capacidadeCemiterios": 0, "cremacaoSemanal": 105, "cemiterios": 1},
                             "educacao": {"fundamental": [1250, 1365, 88], "medio": [1900, 910, 41], "superior": [2400, 4095, 62], "bibliotecas": [0, 0]},
                             "policia": {"presos": 28, "celas": 40, "taxaCrime": 9}},
                "ambiente": {"poluicaoSolo": 6, "valorTerreno": 38, "recursos": {"minerio": [0, 61000], "petroleo": [0, 0], "floresta": [0, 82000], "soloFertil": [0, 240000], "agua": 91000}},
                "comercioExterior": {"importTotal": 410, "exportTotal": 95,
                                     "importa": {"minerio": 9000, "petroleo": 11000, "madeira": 14000, "agricola": 31000, "mercadorias": 86000, "correio": 0, "peixe": 0},
                                     "exporta": {"minerio": 0, "petroleo": 0, "madeira": 0, "agricola": 0, "mercadorias": 21000, "correio": 0, "peixe": 0}},
                "industria": {"generica": [1280, 61], "agricola": [0, 0], "florestal": [0, 0], "minerio": [0, 0], "petroleo": [0, 0]},
                "predios": {"total": len(B), "abandonados": probs.get("Abandoned", [0])[0], "queimados": 0, "desabados": 0,
                            "porServico": {s: sum(1 for r in B if CLASSES[r[5]].split("/")[0] == s) for s in sorted({c.split("/")[0] for c in CLASSES})}, "problemas": probs},
                "transito": {"media": sum(s[7] for s in roads) // len(roads), "trechos": len(roads), "acima50": sum(1 for s in roads if s[7] >= 50), "acima90": sum(1 for s in roads if s[7] >= 90),
                             "veiculos": 1840, "estacionados": 3120,
                             "porTipo": {k.split("|")[0]: [sum(1 for s in roads if s[6] == i), sum(s[7] for s in roads if s[6] == i) // max(1, sum(1 for s in roads if s[6] == i))] for i, k in enumerate(self.kinds) if i in (0, 1, 2, 6)},
                             "piores": [[s[8], s[7], self.streets[s[9]] if s[9] >= 0 else "", self.kinds[s[6]].split("|")[0], s[2], s[3]] for s in worst]},
                "transporte": {"passageiros": {"Bus": [820, 40], "Metro": [1930, 110]},
                               "linhas": [[1, "Bus", "Line 1 Old Town loop", 7, 820, 40, True], [2, "Metro", "Metro Heights to Foundry", 4, 1930, 110, True], [3, "Bus", "Line 3", 2, 0, 0, False]]},
                "conexoes": [["Rodovia", -8649, -1300, True, False, 1], ["Rodovia", 8649, -1300, False, True, 1], ["Train", -8644, 1300, True, True, -1], ["Train", 8644, 1300, True, True, -1],
                             ["Rodovia", 2400, 8649, True, True, 0], ["Ship", -8653, -1050, True, True, -1]],
                "distritos": [[d[3], d[0], [9100, 1200, 4300][i], [52, 21, 44][i], [86, 71, 83][i], [6, 14, 5][i], ["", "Forest Industry", ""][i], d[1], d[2]] for i, d in enumerate(self.districts)],
                "parques": 0,
                "limites": {"predios": [len(B), 49152], "trechosDeRede": [len(self.segs), 36864], "nos": [len(self.segs) // 2, 32768], "blocosDeZona": [1400, 49152], "veiculos": [1840, 16384],
                            "estacionados": [3120, 32768], "cidadaos": [pop + 800, 1048576], "pedestresAtivos": [2100, 65536], "arvores": [48000, 262144], "linhas": [3, 256], "distritos": [3, 128]},
                }

    def servicos(self):
        out = []
        stats = {"Wind Turbine": "Power output: 7 MW", "Solar Power Plant": "Power output: 16 MW", "Incineration Plant": "Garbage reserves: 91000 / 400000\nProcessing rate: 30720 / week\nGarbage trucks in use: 9 / 18",
                 "Landfill Site": "Garbage: 384000 / 400000\nGarbage trucks in use: 0 / 15", "Medical Clinic": "Patients: 63 / 100\nAmbulances in use: 5 / 8", "Crematorium": "Bodies stored: 0 / 105\nHearses in use: 7 / 7",
                 "Fire House": "Fire trucks in use: 1 / 6", "Police Station": "Criminals in jail: 14 / 20\nPolice cars in use: 6 / 10", "Elementary School": "Students: 250 / 273",
                 "High School": "Students: 910 / 910", "University": "Students: 2400 / 4095", "Small Park": "Visitors last week: 18", "Plaza with Trees": "Visitors last week: 31",
                 "Bus Depot": "Vehicles in use: 9", "Water Pumping Station": "Pumping rate: 120000 m³/week", "Water Drain Pipe": "Draining rate: 120000 m³/week", "Statue of Industry": "Visitors last week: 52"}
        for b in self.services:
            name, upkeep, jobs, _, _ = b["svc"]
            out.append([b["id"], name, CLASSES[b["cls"]].split("/")[0], b["x"], b["z"], "LandfillFull" if name == "Landfill Site" else "", stats.get(name, ""), upkeep, jobs, True])
        return {"carregado": True, "predios": out}

    def historico(self):
        cols = ["data", "pop", "caixa", "receita", "despesa", "demR", "demC", "demW", "desemprego", "felicidade", "empregos", "moradias", "valorTerreno", "crime"]
        n, rows, r = 160 + self.weeks(), [], random.Random(3)
        for i in range(n):
            g = 1 / (1 + math.exp(-(i - 70) / 22.0))
            pop = int(16000 * g) + i * 3
            inc, exp = int(41000 * g) + 300, int(36000 * g) + 2800 + (2500 if 60 < i < 85 else 0)
            rows.append(",".join(str(v) for v in [self.date(n - 1 - i), pop, 70000 + int(sum((41000 - 36000) * (1 / (1 + math.exp(-(k - 70) / 22.0))) - 2500 for k in range(i))) // 3 + 30000,
                                                  inc, exp, int(50 + 40 * math.sin(i / 9.0)), int(40 + 30 * math.sin(i / 7.0 + 1)), int(30 + 25 * math.sin(i / 11.0 + 2)),
                                                  max(2, int(14 - 9 * g + 3 * math.sin(i / 6.0))), int(60 + 22 * g + r.randint(-2, 2)), int(7000 * g), int(5200 * g), int(38 * g) + 2, max(3, int(16 - 8 * g))]))
        return {"cidade": "Mockville", "colunas": cols, "linhas": rows}

    def dianoite(self):
        hour = (time.time() / 6.0) % 24
        night = hour < 5 or hour > 20
        j = lambda d: d * (0.97 + 0.06 * random.random())
        pair = lambda dd, dc, nd, nc: [[j(dd), dc, 100.0 * dd / dc * 1.07 if dc else 0], [j(nd), nc, 100.0 * nd / nc * 1.07 if nc else 0]]
        return {"carregado": True, "cidade": "Mockville", "ciclo": True, "noite": night, "hora": hour, "amostras": [420 + self.weeks(), 250 + self.weeks()], "segundosPorAmostra": 2,
                "itens": {"energia": pair(31000, 46000, 41200, 44000), "agua": pair(118000, 160000, 84000, 160000), "esgoto": pair(117000, 180000, 83000, 180000),
                          "lixo": pair(58000, 61440, 51000, 49152), "saude": pair(190, 300, 170, 300), "celas": pair(28, 40, 30, 40), "ensino": pair(5550, 6370, 5550, 5750),
                          "vLixo": pair(21, 33, 9, 27), "vSaude": pair(9, 24, 3, 24), "vFuneraria": pair(7, 7, 6, 7), "vBombeiro": pair(2, 18, 1, 18), "vPolicia": pair(11, 20, 17, 20),
                          "vRuas": pair(0, 0, 0, 0), "trafego": pair(24, 100, 9, 100), "movimento": pair(2100, 0, 800, 0)}}


def page(web):
    index = os.path.join(web, "index.html")
    src = os.path.join(web, "src")
    if os.path.isdir(src):                       # assemble the page the same way build.sh does
        base = open(os.path.join(src, "base.html"), encoding="utf-8").read()
        css = open(os.path.join(src, "estilo.css"), encoding="utf-8").read()
        js = "\n".join(open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(src, "*.js"))))
        return base.replace("/*@@CSS@@*/", css).replace("/*@@JS@@*/", js)
    return open(index, encoding="utf-8").read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=19681)
    ap.add_argument("--web", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web"))
    args = ap.parse_args()
    city = City()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            route = {"/api/cidade": city.cidade, "/api/mapa": city.mapa, "/api/servicos": city.servicos, "/api/historico": city.historico, "/api/dianoite": city.dianoite}.get(path)
            t0 = time.time()
            if path in ("/", "/index.html"):
                body, kind, code = page(args.web).encode("utf-8"), "text/html; charset=utf-8", 200
            elif route:
                body, kind, code = json.dumps(route(), ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json; charset=utf-8", 200
            else:
                body, kind, code = b'{"erro":"not found"}', "application/json; charset=utf-8", 404
            self.send_response(code)
            self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            if route:
                self.send_header("X-Coleta-Ms", str(int((time.time() - t0) * 1000)))
            self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass

    print("mock city at http://127.0.0.1:%d  (page from %s)  Ctrl+C to stop" % (args.port, args.web))
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
