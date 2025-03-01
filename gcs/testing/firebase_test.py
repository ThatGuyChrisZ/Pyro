import firebase_admin
from firebase_admin import credentials, db

cred = credentials.Certificate("gcs/firebase_credentials.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://pyro-fire-tracking-default-rtdb.firebaseio.com/"
})

ref = db.reference("wildfires")

# test entry
ref.push({
    "name": "Test Fire",
    "latitude": 39.5,
    "longitude": -119.8,
    "high_temp": 102.5,
    "low_temp": 78.3,
    "alt": 1200
})

print("🔥 Fire data uploaded to Firebase!")
