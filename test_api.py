import requests
import json

# URL API
BASE_URL = "http://127.0.0.1:8000"

def test_root():
    """Test root endpoint"""
    response = requests.get(f"{BASE_URL}/")
    print("Root endpoint:", response.status_code)
    print(response.json())
    print("-" * 50)

def test_data():
    """Test data endpoint"""
    response = requests.get(f"{BASE_URL}/data")
    print("Data endpoint:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_gejala():
    """Test gejala endpoint"""
    response = requests.get(f"{BASE_URL}/gejala")
    print("Gejala endpoint:", response.status_code)
    print(f"Total gejala: {len(response.json())}")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_diagnosa(data):
    """Test diagnosa endpoint with provided data"""
    response = requests.post(f"{BASE_URL}/diagnosa", json=data)
    print(f"Diagnosa endpoint ({json.dumps(data)}): {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        print(f"Matched rules: {result['matched_rules']}")
        print("\nGejala detail:")
        for code, desc in result['gejala_detail'].items():
            print(f"  - {code}: {desc}")
        print("\nPenyebab:")
        for code, desc in result['penyebab'].items():
            print(f"  - {code}: {desc}")
        print("\nSolusi:")
        for code, desc in result['solusi'].items():
            print(f"  - {code}: {desc}")
    else:
        print("Error:", response.text)
    print("-" * 50)

if __name__ == "__main__":
    print("=" * 50)
    print("TESTING SISTEM DIAGNOSA KERUSAKAN POMPA API")
    print("=" * 50)
    
    # Test the basic endpoints
    test_root()
    test_data()
    test_gejala()
    
    # Test some diagnosa cases
    print("\n" + "=" * 50)
    print("TEST CASE 1: Kavitasi, Korosi, Keausan, Deformasi dengan Impeller dan Centrifugal Pump")
    print("=" * 50)
    test_diagnosa({
        "gejala": ["Kavitasi", "Korosi", "Keausan", "Deformasi"],
        "komponen": "Impeller",
        "jenis_pompa": "Centrifugal Pump"
    })
    
    print("\n" + "=" * 50)
    print("TEST CASE 2: Korosi, Keausan, Retak dengan Piston dan Positive Displacement Pump")
    print("=" * 50)
    test_diagnosa({
        "gejala": ["Korosi", "Keausan", "Retak"],
        "komponen": "Piston",
        "jenis_pompa": "Positive Displacement Pump"
    })
    
    print("\n" + "=" * 50)
    print("TEST CASE 3: Hanya Gejala Keausan, Kebocoran, Retak")
    print("=" * 50)
    test_diagnosa({
        "gejala": ["Keausan", "Kebocoran", "Retak"]
    })
    
    print("\n" + "=" * 50)
    print("TEST CASE 4: Gejala tidak valid")
    print("=" * 50)
    test_diagnosa({
        "gejala": ["Kerusakan Tidak Ada"]
    })