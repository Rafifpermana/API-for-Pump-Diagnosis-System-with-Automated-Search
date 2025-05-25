from fastapi import FastAPI, HTTPException, Query
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

class FilteredOptionsResponse(BaseModel):
    komponen: Dict[str, str]
    gejala: Dict[str, str]

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
                        'conditions': [c.strip() for c in parts[1].split(',') if c.strip()],
                        'results': [r.strip() for r in parts[2].split(',') if r.strip()],
                        'solutions': [s.strip() for s in parts[3].split(',') if s.strip()]
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

@app.get("/filtered-options", response_model=FilteredOptionsResponse)
def get_filtered_options(jenis_pompa: str = Query(..., description="Jenis pompa untuk filter")):
    """
    Mendapatkan komponen dan gejala yang tersedia berdasarkan jenis pompa
    """
    try:
        # Konversi jenis pompa ke kode
        jenis_code = data_store.jenis_pompa_reverse.get(jenis_pompa.lower().strip())
        if not jenis_code:
            raise HTTPException(400, detail=f"Jenis pompa tidak valid: {jenis_pompa}")
        
        # Cari aturan yang menggunakan jenis pompa ini
        available_komponen = set()
        available_gejala = set()
        
        for rule in data_store.aturan:
            # Cek apakah aturan ini untuk jenis pompa yang dipilih
            if jenis_code in rule['conditions']:
                # Ambil komponen dari kondisi
                for condition in rule['conditions']:
                    if condition.startswith('K'):
                        available_komponen.add(condition)
                    elif condition.startswith('R'):
                        available_gejala.add(condition)
        
        # Konversi kode ke deskripsi
        filtered_komponen = {
            code: data_store.komponen.get(code, "Tidak diketahui") 
            for code in available_komponen
        }
        filtered_gejala = {
            code: data_store.diagnosa.get(code, "Tidak diketahui") 
            for code in available_gejala
        }
        
        return FilteredOptionsResponse(
            komponen=filtered_komponen,
            gejala=filtered_gejala
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dalam get_filtered_options: {str(e)}")
        raise HTTPException(500, detail="Terjadi kesalahan internal")

@app.get("/filtered-gejala")
def get_filtered_gejala(
    jenis_pompa: str = Query(..., description="Jenis pompa untuk filter"),
    komponen: Optional[str] = Query(None, description="Komponen untuk filter lebih lanjut")
):
    """
    Mendapatkan gejala yang tersedia berdasarkan jenis pompa dan komponen (opsional)
    """
    try:
        # Konversi input ke kode
        jenis_code = data_store.jenis_pompa_reverse.get(jenis_pompa.lower().strip())
        if not jenis_code:
            raise HTTPException(400, detail=f"Jenis pompa tidak valid: {jenis_pompa}")
        
        komponen_code = None
        if komponen:
            komponen_code = data_store.komponen_reverse.get(komponen.lower().strip())
            if not komponen_code:
                raise HTTPException(400, detail=f"Komponen tidak valid: {komponen}")
        
        # Cari gejala yang tersedia
        available_gejala = set()
        
        for rule in data_store.aturan:
            # Cek apakah aturan sesuai dengan filter
            rule_match = jenis_code in rule['conditions']
            
            if komponen_code:
                rule_match = rule_match and komponen_code in rule['conditions']
            
            if rule_match:
                for condition in rule['conditions']:
                    if condition.startswith('R'):
                        available_gejala.add(condition)
        
        # Konversi ke deskripsi
        filtered_gejala = {
            code: data_store.diagnosa.get(code, "Tidak diketahui") 
            for code in available_gejala
        }
        
        return filtered_gejala
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dalam get_filtered_gejala: {str(e)}")
        raise HTTPException(500, detail="Terjadi kesalahan internal")

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
        
        # Pencocokan aturan dengan prioritas
        matched_rules = []
        
        for rule in data_store.aturan:
            match = True
            
            # Cek jenis pompa (wajib jika ada)
            if jenis_code and any(c.startswith('V') for c in rule['conditions']):
                if jenis_code not in rule['conditions']:
                    match = False
                    continue
            
            # Cek komponen (opsional, tapi jika ada harus cocok)
            if komponen_code and any(c.startswith('K') for c in rule['conditions']):
                if komponen_code not in rule['conditions']:
                    match = False
                    continue
            
            # Cek gejala - semua gejala yang dipilih harus ada dalam kondisi rule
            rule_gejala = [c for c in rule['conditions'] if c.startswith('R')]
            gejala_match_count = sum(1 for g in gejala_codes if g in rule_gejala)
            
            # Rule cocok jika minimal 70% gejala yang dipilih ada dalam rule
            if len(gejala_codes) > 0:
                match_percentage = gejala_match_count / len(gejala_codes)
                if match_percentage < 0.7:  # Minimal 70% kecocokan
                    match = False
                    continue
            
            if match and gejala_match_count > 0:
                matched_rules.append({
                    'rule_id': rule['rule'],
                    'match_score': gejala_match_count,
                    'match_percentage': match_percentage if len(gejala_codes) > 0 else 0
                })
        
        # Urutkan berdasarkan skor kecocokan
        matched_rules.sort(key=lambda x: (x['match_score'], x['match_percentage']), reverse=True)
        
        # Ambil hanya rule ID untuk response
        rule_ids = [r['rule_id'] for r in matched_rules[:5]]  # Maksimal 5 rule terbaik
        
        # Bangun response
        penyebab = {}
        solusi = {}
        
        for rule in data_store.aturan:
            if rule['rule'] in rule_ids:
                for p in rule['results']:
                    if p in data_store.penyebab:
                        penyebab[p] = data_store.penyebab[p]
                for s in rule['solutions']:
                    if s in data_store.solusi:
                        solusi[s] = data_store.solusi[s]
        
        return DiagnosaResponse(
            matched_rules=rule_ids,
            gejala_detail={code: data_store.diagnosa[code] for code in gejala_codes if code in data_store.diagnosa},
            penyebab=penyebab,
            solusi=solusi,
            success=len(rule_ids) > 0,
            message=f"Diagnosa berhasil dengan {len(rule_ids)} aturan yang cocok" if rule_ids else "Tidak ada aturan yang cocok dengan gejala yang dipilih"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(500, detail="Terjadi kesalahan internal")

@app.get("/")
def read_root():
    """Root endpoint for testing API connectivity"""
    return {
        "status": "success",
        "message": "Sistem Diagnosa Kerusakan Pompa API is running",
        "endpoints": [
            {"method": "GET", "path": "/", "description": "This endpoint"},
            {"method": "GET", "path": "/gejala", "description": "List all gejala/symptoms"},
            {"method": "GET", "path": "/komponen", "description": "List all komponen/components"},
            {"method": "GET", "path": "/jenis-pompa", "description": "List all pump types"},
            {"method": "GET", "path": "/filtered-options", "description": "Get filtered components and symptoms by pump type"},
            {"method": "GET", "path": "/filtered-gejala", "description": "Get filtered symptoms by pump type and component"},
            {"method": "POST", "path": "/diagnosa", "description": "Diagnose pump issues from symptoms"}
        ]
    }

@app.get("/data")
def get_data():
    """Endpoint that returns all available data"""
    return {
        "gejala": data_store.diagnosa,
        "komponen": data_store.komponen,
        "jenis_pompa": data_store.jenis_pompa,
        "penyebab": data_store.penyebab,
        "solusi": data_store.solusi,
        "total_rules": len(data_store.aturan)
    }

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)