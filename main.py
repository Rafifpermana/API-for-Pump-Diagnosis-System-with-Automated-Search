from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import csv
import os
import uvicorn
import logging
from fastapi.middleware.cors import CORSMiddleware

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sistem Diagnosa Kerusakan Pompa",
    description="API untuk diagnosa kerusakan pompa berbasis gejala",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DataStore:
    def __init__(self):
        self.diagnosa = {}
        self.diagnosa_reverse = {}
        self.penyebab = {}
        self.penyebab_reverse = {}
        self.solusi = {}
        self.solusi_reverse = {}
        self.komponen = {}
        self.komponen_reverse = {}
        self.jenis_pompa = {}
        self.jenis_pompa_reverse = {}
        self.aturan = []

data_store = DataStore()
DATA_DIR = "data"

class DiagnosaRequest(BaseModel):
    gejala: List[str]
    komponen: Optional[str] = None
    jenis_pompa: Optional[str] = None

class DiagnosaResponse(BaseModel):
    matched_rules: List[int]
    gejala_detail: Dict[str, str]
    penyebab: Dict[str, str]
    solusi: Dict[str, str]
    success: bool
    message: str

def load_csv(file_path: str, forward: dict, reverse: dict):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            sample = f.read(1024)
            f.seek(0)
            delimiter = max([',', ';', '\t'], key=lambda x: sample.count(x))
            reader = csv.DictReader(f, delimiter=delimiter)
            
            if not {'Variabel', 'Keterangan'}.issubset(reader.fieldnames):
                raise ValueError("Format header tidak valid")
            
            for row in reader:
                var = row['Variabel'].strip()
                ket = row['Keterangan'].strip()
                if var and ket:
                    forward[var] = ket
                    reverse[ket.lower()] = var
    except Exception as e:
        logger.error(f"Gagal memuat {file_path}: {str(e)}")
        raise

def load_rules(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = [line.strip() for line in f if line.strip()]
            header_idx = next((i for i, line in enumerate(lines) if "RULE" in line), 0)
            delimiter = ',' if ',' in lines[header_idx] else ';'
            
            rules = []
            for line in lines[header_idx+1:]:
                if line.startswith(('#', ';')) or not line:
                    continue
                parts = line.split(delimiter)
                if len(parts) >= 4 and parts[0].strip().isdigit():
                    rules.append({
                        'rule': int(parts[0].strip()),
                        'conditions': [c.strip() for c in parts[1].split(',')],
                        'results': [r.strip() for r in parts[2].split(',')],
                        'solutions': [s.strip() for s in parts[3].split(',')]
                    })
            return rules
    except Exception as e:
        logger.error(f"Gagal memuat aturan: {str(e)}")
        raise

def initialize_data():
    try:
        # Load data utama
        datasets = [
            ('diagnosa kerusakan.csv', data_store.diagnosa, data_store.diagnosa_reverse),
            ('penyebab kerusakan.csv', data_store.penyebab, data_store.penyebab_reverse),
            ('solusi kerusakan.csv', data_store.solusi, data_store.solusi_reverse),
            ('komponen pompa.csv', data_store.komponen, data_store.komponen_reverse),
            ('jenis pompa.csv', data_store.jenis_pompa, data_store.jenis_pompa_reverse)
        ]
        
        for filename, fwd, rev in datasets:
            load_csv(os.path.join(DATA_DIR, filename), fwd, rev)
        
        # Load aturan
        data_store.aturan = load_rules(os.path.join(DATA_DIR, "aturan kerusakan dan solusi.csv"))
        
        logger.info("Data terload:")
        logger.info(f"- Gejala: {len(data_store.diagnosa)} item")
        logger.info(f"- Penyebab: {len(data_store.penyebab)} item")
        logger.info(f"- Solusi: {len(data_store.solusi)} item")
        logger.info(f"- Komponen: {len(data_store.komponen)} item")
        logger.info(f"- Jenis Pompa: {len(data_store.jenis_pompa)} item")
        logger.info(f"- Aturan: {len(data_store.aturan)} item")
        
    except Exception as e:
        logger.critical(f"Gagal inisialisasi data: {str(e)}")
        raise

@app.on_event("startup")
async def startup():
    initialize_data()

@app.get("/gejala")
def get_gejala():
    return data_store.diagnosa

@app.get("/komponen")
def get_komponen():
    return data_store.komponen

@app.get("/jenis-pompa")
def get_jenis_pompa():
    return data_store.jenis_pompa

@app.post("/diagnosa", response_model=DiagnosaResponse)
async def diagnosa(request: DiagnosaRequest):
    try:
        # Konversi input ke kode
        gejala_codes = []
        for gejala in request.gejala:
            gejala_lower = gejala.lower().strip()
            code = data_store.diagnosa_reverse.get(gejala_lower)
            if not code:
                raise HTTPException(400, detail=f"Gejala tidak valid: {gejala}")
            gejala_codes.append(code)
        
        komponen_code = None
        if request.komponen:
            komponen_lower = request.komponen.lower().strip()
            komponen_code = data_store.komponen_reverse.get(komponen_lower)
            if not komponen_code:
                raise HTTPException(400, detail=f"Komponen tidak valid: {request.komponen}")
        
        jenis_code = None
        if request.jenis_pompa:
            jenis_lower = request.jenis_pompa.lower().strip()
            jenis_code = data_store.jenis_pompa_reverse.get(jenis_lower)
            if not jenis_code:
                raise HTTPException(400, detail=f"Jenis pompa tidak valid: {request.jenis_pompa}")
        
        # Pencocokan aturan
        matched_rules = []
        for rule in data_store.aturan:
            match = True
            # Cek komponen
            if komponen_code and any(c.startswith('K') for c in rule['conditions']):
                if komponen_code not in rule['conditions']:
                    match = False
            # Cek jenis pompa
            if jenis_code and any(c.startswith('V') for c in rule['conditions']):
                if jenis_code not in rule['conditions']:
                    match = False
            # Cek gejala
            for condition in rule['conditions']:
                if condition.startswith('R') and condition not in gejala_codes:
                    match = False
                    break
            if match:
                matched_rules.append(rule['rule'])
        
        # Bangun response
        penyebab = {}
        solusi = {}
        for rule in data_store.aturan:
            if rule['rule'] in matched_rules:
                for p in rule['results']:
                    penyebab[p] = data_store.penyebab.get(p, "Tidak diketahui")
                for s in rule['solutions']:
                    solusi[s] = data_store.solusi.get(s, "Tidak diketahui")
        
        return DiagnosaResponse(
            matched_rules=matched_rules,
            gejala_detail={code: data_store.diagnosa[code] for code in gejala_codes},
            penyebab=penyebab,
            solusi=solusi,
            success=len(matched_rules) > 0,
            message="Diagnosa berhasil" if matched_rules else "Tidak ada aturan yang cocok"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(500, detail="Terjadi kesalahan internal")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)