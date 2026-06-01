"""Check Bouvron transactions with chatbot-like SQL."""
import os, psycopg2, psycopg2.extras
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Test 1: Exact query the LLM would generate
cur.execute("""
    SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
           COUNT(*) AS nb_transactions
    FROM transactions t
    JOIN communes_stats c ON t.commune_code = c.commune_code
    WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'bouvron'
      AND t.est_valide = TRUE
      AND t.prix_m2 IS NOT NULL
      AND t.date_mutation >= NOW() - INTERVAL '24 months'
""")
print("=== Test 1: translate+lower match (24 months) ===")
print(dict(cur.fetchone()))

# Test 2: lower only
cur.execute("""
    SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
           COUNT(*) AS nb_transactions
    FROM transactions t
    JOIN communes_stats c ON t.commune_code = c.commune_code
    WHERE lower(c.nom_commune) = 'bouvron'
      AND t.est_valide = TRUE
      AND t.prix_m2 IS NOT NULL
      AND t.date_mutation >= NOW() - INTERVAL '24 months'
""")
print("\n=== Test 2: lower match (24 months) ===")
print(dict(cur.fetchone()))

# Test 3: ILIKE
cur.execute("""
    SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
           COUNT(*) AS nb_transactions
    FROM transactions t
    JOIN communes_stats c ON t.commune_code = c.commune_code
    WHERE c.nom_commune ILIKE 'bouvron'
      AND t.est_valide = TRUE
      AND t.prix_m2 IS NOT NULL
      AND t.date_mutation >= NOW() - INTERVAL '24 months'
""")
print("\n=== Test 3: ILIKE match (24 months) ===")
print(dict(cur.fetchone()))

# Check what nom_commune actually looks like
cur.execute("SELECT nom_commune, length(nom_commune) FROM communes_stats WHERE commune_code = '44023'")
row = cur.fetchone()
print(f"\n=== Actual nom_commune ===")
print(f"Value: '{row['nom_commune']}' (length={row['length']})")
print(f"Bytes: {row['nom_commune'].encode('utf-8')}")

conn.close()
